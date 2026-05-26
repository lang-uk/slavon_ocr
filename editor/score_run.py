#!/usr/bin/env python3
"""Score an isolated run directory against human-proofread refs from cards.db.

Reads output JSONs from output/<source>/runs/<run-id>/, fetches the matching
proofread `lines` and `source_reference` from the DB, applies the same
cleaning/source-line-stripping as eval_cer.py and eval_setup.py, and emits
editor/runs/<run-id>/summary.json containing:
  - per-card CER (flat) + errors + ref_chars
  - aggregate micro-CER (flat)
  - top substitutions / insertions / deletions (character level)
  - which cards failed (no valid output in the run dir)

Also reports micro-WER (flat) using spacy's Ukrainian tokenizer
(uk_core_news_sm), matching the tokenization used in eval_cer.py. Run
under the project venv so spacy + rapidfuzz are available.

Usage:
    python editor/score_run.py --run-id baseline
    python editor/score_run.py --run-id v1
"""

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

import spacy
from rapidfuzz.distance import Levenshtein

from eval_setup import (
    clean,
    flatten,
    strip_source_line,
    extract_ocr_lines,
)

_NLP = None


def _nlp():
    global _NLP
    if _NLP is None:
        _NLP = spacy.load("uk_core_news_sm")
    return _NLP


def tokenize(text: str) -> list[str]:
    """Tokenize via spacy uk; drop whitespace and punctuation tokens."""
    return [t.text for t in _nlp()(text) if not (t.is_space or t.is_punct)]

REPO = Path(__file__).resolve().parent.parent
HERE = Path(__file__).parent
DB_PATH = HERE / "cards.db"
RUNS_META_DIR = HERE / "runs"


def editops(a: str, b: str):
    """Return list of (op, i, j): op in {'eq','sub','del','ins'}."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        ai = a[i - 1]
        for j in range(1, m + 1):
            if ai == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and a[i - 1] == b[j - 1]:
            i -= 1
            j -= 1
            # 'eq' not emitted; saves memory
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            ops.append(("sub", i - 1, j - 1))
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(("del", i - 1, j - 1))
            i -= 1
        else:
            ops.append(("ins", i - 1, j - 1))
            j -= 1
    ops.reverse()
    return ops


def load_proofs_from_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT folder, filename, lines, source_reference FROM cards "
        "WHERE reviewed = 1 AND deleted = 0 AND lines IS NOT NULL"
    ).fetchall()
    conn.close()
    return {f"{r['folder']}/{r['filename']}": dict(r) for r in rows}


def load_run_output(path: Path) -> str:
    """Load a run's JSON file and return its flattened lines string, or ''."""
    try:
        data = json.loads(path.read_text())
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    lines = data.get("lines")
    if not lines:
        return ""
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--source-folder", default=None,
                    help="Override source folder; defaults to manifest's")
    args = ap.parse_args()

    manifest_path = RUNS_META_DIR / f"{args.run_id}.json"
    if not manifest_path.exists():
        raise SystemExit(f"No manifest at {manifest_path} — did eval_run.py run?")
    manifest = json.loads(manifest_path.read_text())
    source_folder = args.source_folder or manifest["source_folder"]
    run_dir = REPO / "output" / source_folder / "runs" / args.run_id

    proofs = load_proofs_from_db()
    records = manifest["records"]

    per_card = []
    total_chars = 0
    total_errors = 0
    total_words = 0
    total_word_errors = 0
    subs = Counter()      # (ref_char, hyp_char) -> count
    ins = Counter()       # hyp_char -> count (extra in OCR)
    dels = Counter()      # ref_char -> count (missing from OCR)
    failures = []

    for rec in records:
        key = rec["key"]
        filename = rec["filename"]
        json_path = run_dir / (Path(filename).stem + ".json")
        proof = proofs.get(key)
        if not proof:
            failures.append({"key": key, "reason": "no_proof_in_db"})
            continue

        ref_raw = proof["lines"] or ""
        ref = strip_source_line(clean(ref_raw), proof["source_reference"])
        ref_flat = flatten(ref)

        ref_tokens = tokenize(ref_flat)
        n_words = len(ref_tokens) or 1

        hyp_raw = load_run_output(json_path)
        if not hyp_raw:
            failures.append({"key": key, "reason": rec.get("final_status", "missing_output")})
            # Still count it as 100%-error against the ref for honesty
            dist = len(ref_flat)
            n = len(ref_flat) or 1
            word_dist = len(ref_tokens)
            per_card.append({
                "key": key,
                "cer_flat": dist / n,
                "wer_flat": word_dist / n_words,
                "errors": dist,
                "ref_chars": n,
                "word_errors": word_dist,
                "ref_words": n_words,
                "status": "missing_output",
            })
            total_chars += n
            total_errors += dist
            total_words += n_words
            total_word_errors += word_dist
            continue

        hyp = strip_source_line(clean(hyp_raw), proof["source_reference"])
        hyp_flat = flatten(hyp)
        hyp_tokens = tokenize(hyp_flat)

        ops = editops(ref_flat, hyp_flat)
        dist = len(ops)
        n = len(ref_flat) or 1
        word_dist = Levenshtein.distance(ref_tokens, hyp_tokens)

        for op, i, j in ops:
            if op == "sub":
                subs[(ref_flat[i], hyp_flat[j])] += 1
            elif op == "ins":
                ins[hyp_flat[j]] += 1
            elif op == "del":
                dels[ref_flat[i]] += 1

        total_chars += n
        total_errors += dist
        total_words += n_words
        total_word_errors += word_dist
        per_card.append({
            "key": key,
            "cer_flat": dist / n,
            "wer_flat": word_dist / n_words,
            "errors": dist,
            "ref_chars": n,
            "word_errors": word_dist,
            "ref_words": n_words,
            "status": "scored",
        })

    micro_cer = total_errors / total_chars if total_chars else 0.0
    micro_wer = total_word_errors / total_words if total_words else 0.0
    per_card.sort(key=lambda p: -p["cer_flat"])

    summary = {
        "run_id": args.run_id,
        "prompt": manifest["prompt"],
        "source_folder": source_folder,
        "n_cards": len(records),
        "n_scored": sum(1 for p in per_card if p["status"] == "scored"),
        "n_failed_to_produce_output": len(failures),
        "total_ref_chars": total_chars,
        "total_errors": total_errors,
        "total_ref_words": total_words,
        "total_word_errors": total_word_errors,
        "micro_cer_flat": micro_cer,
        "micro_wer_flat": micro_wer,
        "per_card": per_card,
        "top_substitutions": [
            {"ref": rc, "hyp": hc, "count": c, "ref_cp": f"U+{ord(rc):04X}", "hyp_cp": f"U+{ord(hc):04X}"}
            for (rc, hc), c in subs.most_common(30)
        ],
        "top_insertions": [
            {"char": ch, "count": c, "cp": f"U+{ord(ch):04X}"}
            for ch, c in ins.most_common(20)
        ],
        "top_deletions": [
            {"char": ch, "count": c, "cp": f"U+{ord(ch):04X}"}
            for ch, c in dels.most_common(20)
        ],
        "failures": failures,
    }

    out_path = RUNS_META_DIR / f"{args.run_id}.summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    print(f"run {args.run_id}: {summary['n_scored']}/{summary['n_cards']} scored")
    print(f"  micro CER (flat): {micro_cer:.2%}  ({total_errors}/{total_chars})")
    print(f"  micro WER (flat): {micro_wer:.2%}  ({total_word_errors}/{total_words})")
    if failures:
        print(f"  failures: {len(failures)}")
        for f in failures[:5]:
            print(f"    {f['key']:30} {f['reason']}")
    print(f"  worst 5 scored:")
    for p in per_card[:5]:
        print(f"    {p['key']:30} cer={p['cer_flat']:.1%}  ({p['errors']}/{p['ref_chars']})")
    print(f"  top subs:")
    for s in summary["top_substitutions"][:8]:
        print(f"    {s['ref']!r:>4} -> {s['hyp']!r:<4} x{s['count']}")
    print(f"\nwrote {out_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
