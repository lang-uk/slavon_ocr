#!/usr/bin/env python3
"""One-shot setup for the prompt-iteration eval loop.

Reads reviewed Пересторога cards from cards.db and emits:
  - editor/baseline_scores.json: per-card CER of the current (frozen) OCR
    output stored in `original_json` vs the human-proofread `lines`. No
    model calls; this is pure string comparison.
  - editor/splits.json: a frozen {seed, dev, test} 80/20 split over the
    reviewed pool, keyed by "<folder>/<filename>".

CER here is computed flat (line breaks dropped) after the same cleaning
and source-reference stripping that eval_cer.py does, so numbers line up
with the existing HTML report. Pure-python Levenshtein — no spacy/rapidfuzz
dependency so this runs anywhere.

Usage:
    python editor/eval_setup.py
    python editor/eval_setup.py --seed 0 --test-ratio 0.2
"""

import argparse
import json
import random
import re
import sqlite3
from pathlib import Path


HERE = Path(__file__).parent
DB_PATH = HERE / "cards.db"
SPLITS_PATH = HERE / "splits.json"
BASELINE_PATH = HERE / "baseline_scores.json"


# ---------- text cleaning (kept in sync with eval_cer.py) -------------------

def clean(text):
    text = text.replace("\r", "").strip()
    # Normalize runs of 3+ periods to a single U+2026 ellipsis so the
    # scorer treats "..." and "…" as equivalent. Proofreads mix both
    # forms ~50/50 and model outputs do too; without this fix every
    # mismatch costs 3 spurious ops (2 insertions + 1 substitution).
    text = re.sub(r"\.{3,}", "\u2026", text)
    return text


def flatten(text):
    return re.sub(r"\n+", " ", text)


def normalize_dashes(s):
    return re.sub(r"\s*[-\u2013\u2014]\s*", "-", s)


_SOURCE_LINE_HINTS = ("львів", "львов", "київ", "kyiv", "lviv")
_YEAR_RE = re.compile(r"1[56]\d\d")


def _looks_like_source_line(line: str) -> bool:
    """Heuristic: a source-reference line contains a known city name or an
    early-modern year. Used to strip the last line of a transcription
    without requiring an exact substring match against the DB's source_reference
    field — the earlier strict match was asymmetric when the model mis-read
    a source digit or substituted є/е in the city abbreviation."""
    low = line.lower()
    if any(h in low for h in _SOURCE_LINE_HINTS):
        return True
    if _YEAR_RE.search(low):
        return True
    return False


def strip_source_line(text, source_reference):
    """Remove the trailing source-reference line(s) from a transcription.

    Some models break the source reference across two lines (e.g. "Львів,
    1605-1606, Перест. 28-" / "29"), so we scan the last three lines and
    strip from the earliest one that looks like a source line. This is
    robust to model mis-reads of the source digits, abbrev expansions, or
    line-wraps that would otherwise break strict substring matching and
    cascade dozens of fake errors into the CER.
    """
    ref = (source_reference or "").strip().rstrip(".")
    if not ref:
        return text
    lines = text.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return text

    # Scan up to the last 3 lines looking for a source-line marker.
    # The earliest hit becomes the cut point: strip from there to end.
    cut = None
    for i in range(max(0, len(lines) - 3), len(lines)):
        if _looks_like_source_line(lines[i]):
            cut = i
            break
    if cut is not None:
        return "\n".join(lines[:cut]).strip()

    # Fall back to strict substring match on the last line only.
    last = lines[-1].strip()
    last_low = normalize_dashes(last).lower()
    ref_clean = normalize_dashes(ref).lower()
    if ref_clean in last_low:
        return "\n".join(lines[:-1]).strip()
    return text


def extract_ocr_lines(original_json):
    try:
        data = json.loads(original_json)
    except Exception:
        return ""
    lines = data.get("lines")
    if not lines:
        return ""
    return "\n".join(lines)


def levenshtein(a, b):
    """Classic DP. Returns edit distance between two strings.
    Fine for our sizes (cards are a few hundred chars each)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # rolling two-row DP
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                curr[j - 1] + 1,       # insert
                prev[j] + 1,           # delete
                prev[j - 1] + cost,    # replace
            )
        prev = curr
    return prev[-1]


# ---------- main ------------------------------------------------------------

def load_reviewed(conn):
    return conn.execute(
        "SELECT folder, filename, original_json, lines, source_reference "
        "FROM cards "
        "WHERE reviewed = 1 AND deleted = 0 AND lines IS NOT NULL"
    ).fetchall()


def compute_baseline(rows):
    """Returns list of {key, cer_flat, ref_chars, errors, source_reference}."""
    scored = []
    for r in rows:
        ocr = strip_source_line(clean(extract_ocr_lines(r["original_json"])), r["source_reference"])
        ref = strip_source_line(clean(r["lines"] or ""), r["source_reference"])
        if not ocr and not ref:
            continue
        ocr_f = flatten(ocr)
        ref_f = flatten(ref)
        dist = levenshtein(ref_f, ocr_f)
        n = len(ref_f) or 1
        scored.append({
            "key": f"{r['folder']}/{r['filename']}",
            "folder": r["folder"],
            "filename": r["filename"],
            "source_reference": r["source_reference"],
            "ref_chars": n,
            "errors": dist,
            "cer_flat": dist / n,
        })
    return scored


def make_split(keys, seed, test_ratio):
    rng = random.Random(seed)
    shuffled = sorted(keys)  # deterministic pre-order
    rng.shuffle(shuffled)
    cut = int(round(len(shuffled) * (1 - test_ratio)))
    return {
        "seed": seed,
        "test_ratio": test_ratio,
        "dev": sorted(shuffled[:cut]),
        "test": sorted(shuffled[cut:]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--test-ratio", type=float, default=0.2)
    args = ap.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = load_reviewed(conn)
    conn.close()

    scored = compute_baseline(rows)
    scored.sort(key=lambda s: -s["cer_flat"])

    total_chars = sum(s["ref_chars"] for s in scored)
    total_errors = sum(s["errors"] for s in scored)
    micro_cer = total_errors / total_chars if total_chars else 0.0

    baseline_out = {
        "n_cards": len(scored),
        "micro_cer_flat": micro_cer,
        "per_card": scored,
    }
    BASELINE_PATH.write_text(json.dumps(baseline_out, ensure_ascii=False, indent=2))
    print(f"baseline: {len(scored)} cards, micro CER (flat) = {micro_cer:.2%}")
    print(f"  worst 5:")
    for s in scored[:5]:
        print(f"    {s['key']:30} cer={s['cer_flat']:.1%}  ({s['errors']}/{s['ref_chars']})")
    print(f"  best 5:")
    for s in sorted(scored, key=lambda x: x["cer_flat"])[:5]:
        print(f"    {s['key']:30} cer={s['cer_flat']:.1%}  ({s['errors']}/{s['ref_chars']})")

    keys = [s["key"] for s in scored]
    split = make_split(keys, args.seed, args.test_ratio)
    SPLITS_PATH.write_text(json.dumps(split, ensure_ascii=False, indent=2))
    print(f"\nsplit seed={args.seed}: dev={len(split['dev'])}, test={len(split['test'])}")
    print(f"  wrote {SPLITS_PATH.relative_to(HERE.parent)}")
    print(f"  wrote {BASELINE_PATH.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
