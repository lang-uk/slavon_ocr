#!/usr/bin/env python3
"""Compute CER and WER between original OCR and proofread text for reviewed cards.

Both CER and WER are reported in two variants:
  - flat:  lines concatenated into one string, line breaks ignored
  - lines: line breaks preserved, hyphenated words rejoined across lines

WER uses spacy's Ukrainian tokenizer (uk_core_news_sm).
Whitespace and punctuation tokens are excluded from word counts.
"""

import json
import re
import sys
from collections import defaultdict

import spacy

from db import get_db

nlp = spacy.load("uk_core_news_sm")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def levenshtein(ref, hyp):
    """Levenshtein edit distance between two sequences."""
    n, m = len(ref), len(hyp)
    if n == 0:
        return m
    if m == 0:
        return n

    prev = list(range(m + 1))
    curr = [0] * (m + 1)

    for i in range(1, n + 1):
        curr[0] = i
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,       # deletion
                curr[j - 1] + 1,   # insertion
                prev[j - 1] + cost  # substitution
            )
        prev, curr = curr, prev

    return prev[m]


def clean(text):
    """Strip \\r, normalize whitespace."""
    text = text.replace("\r", "")
    return text.strip()


def flatten(text):
    """Concatenate lines into a single string (no line breaks)."""
    return re.sub(r"\n+", " ", text)


def rejoin_hyphens(text):
    """Rejoin words split across lines with hyphens: 'по-\\nтомныє' -> 'потомныє'."""
    return re.sub(r"-\n", "", text)


def tokenize(text, do_rejoin_hyphens=True):
    """Tokenize with spacy, drop whitespace and punctuation tokens."""
    if do_rejoin_hyphens:
        text = rejoin_hyphens(text)
    doc = nlp(text)
    return [tok.text for tok in doc if not tok.is_space and not tok.is_punct]


def extract_ocr_text(original_json):
    """Extract lines text from the frozen original JSON."""
    data = json.loads(original_json)
    lines = data.get("lines")
    if not lines:
        return ""
    return "\n".join(lines)


def classify_source(row):
    """Group cards by source for reporting."""
    ref = (row["source_reference"] or "").strip().lower()
    if not ref:
        return "unknown"

    if "крон" in ref:
        return "Кройника"
    elif "берест" in ref or "перест" in ref:
        return "Пересторога"
    elif "сак" in ref or "вірш" in ref:
        return "Сак. Вірші"
    else:
        return ref


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM cards WHERE reviewed = 1 AND deleted = 0 AND lines IS NOT NULL"
    ).fetchall()
    conn.close()

    if not rows:
        print("No reviewed cards found.")
        sys.exit(0)

    stats = defaultdict(lambda: {
        "cards": 0,
        "ref_chars_flat": 0, "char_errors_flat": 0,
        "ref_chars_lines": 0, "char_errors_lines": 0,
        "ref_words_flat": 0, "word_errors_flat": 0,
        "ref_words_lines": 0, "word_errors_lines": 0,
        "card_details": [],
    })

    for row in rows:
        ocr_raw = extract_ocr_text(row["original_json"])
        proof_raw = row["lines"] or ""

        # Clean \r from both
        ocr_clean = clean(ocr_raw)
        proof_clean = clean(proof_raw)

        if not ocr_clean and not proof_clean:
            continue

        source = classify_source(row)
        s = stats[source]
        s["cards"] += 1

        # --- CER (flat): no line breaks ---
        proof_flat = flatten(proof_clean)
        ocr_flat = flatten(ocr_clean)
        char_dist_flat = levenshtein(proof_flat, ocr_flat)
        ref_chars_flat = len(proof_flat) or 1

        # --- CER (lines): line breaks preserved ---
        char_dist_lines = levenshtein(proof_clean, ocr_clean)
        ref_chars_lines = len(proof_clean) or 1

        # --- WER (flat): tokenize flattened text (no line breaks, no hyphen rejoining needed) ---
        ref_tokens_flat = tokenize(proof_flat, do_rejoin_hyphens=False)
        hyp_tokens_flat = tokenize(ocr_flat, do_rejoin_hyphens=False)
        word_dist_flat = levenshtein(ref_tokens_flat, hyp_tokens_flat)
        n_ref_words_flat = len(ref_tokens_flat) or 1

        # --- WER (lines): tokenize with line breaks, rejoin hyphens across lines ---
        ref_tokens_lines = tokenize(proof_clean, do_rejoin_hyphens=True)
        hyp_tokens_lines = tokenize(ocr_clean, do_rejoin_hyphens=True)
        word_dist_lines = levenshtein(ref_tokens_lines, hyp_tokens_lines)
        n_ref_words_lines = len(ref_tokens_lines) or 1

        s["ref_chars_flat"] += ref_chars_flat
        s["char_errors_flat"] += char_dist_flat
        s["ref_chars_lines"] += ref_chars_lines
        s["char_errors_lines"] += char_dist_lines
        s["ref_words_flat"] += n_ref_words_flat
        s["word_errors_flat"] += word_dist_flat
        s["ref_words_lines"] += n_ref_words_lines
        s["word_errors_lines"] += word_dist_lines

        s["card_details"].append({
            "filename": row["filename"],
            "cer_flat": char_dist_flat / ref_chars_flat,
            "cer_lines": char_dist_lines / ref_chars_lines,
            "wer_flat": word_dist_flat / n_ref_words_flat,
            "wer_lines": word_dist_lines / n_ref_words_lines,
            "char_errors_flat": char_dist_flat,
            "ref_chars_flat": ref_chars_flat,
            "char_errors_lines": char_dist_lines,
            "ref_chars_lines": ref_chars_lines,
            "word_errors_flat": word_dist_flat,
            "ref_words_flat": n_ref_words_flat,
            "word_errors_lines": word_dist_lines,
            "ref_words_lines": n_ref_words_lines,
            "ref_tokens_flat": ref_tokens_flat,
            "hyp_tokens_flat": hyp_tokens_flat,
            "ref_tokens_lines": ref_tokens_lines,
            "hyp_tokens_lines": hyp_tokens_lines,
        })

    # --- Print report ---
    print("=" * 78)
    print("OCR EVALUATION REPORT")
    print(f"Reviewed cards: {sum(s['cards'] for s in stats.values())}")
    print("Reference: human-proofread | Hypothesis: original OCR")
    print("Tokenizer: spacy uk_core_news_sm (hyphens rejoined, punct excluded)")
    print("=" * 78)

    totals = defaultdict(int)

    for source in sorted(stats.keys()):
        s = stats[source]
        cer_flat = s["char_errors_flat"] / s["ref_chars_flat"] if s["ref_chars_flat"] else 0
        cer_lines = s["char_errors_lines"] / s["ref_chars_lines"] if s["ref_chars_lines"] else 0
        wer_flat = s["word_errors_flat"] / s["ref_words_flat"] if s["ref_words_flat"] else 0
        wer_lines = s["word_errors_lines"] / s["ref_words_lines"] if s["ref_words_lines"] else 0

        for k in ("ref_chars_flat", "char_errors_flat", "ref_chars_lines",
                   "char_errors_lines", "ref_words_flat", "word_errors_flat",
                   "ref_words_lines", "word_errors_lines"):
            totals[k] += s[k]

        print(f"\n--- {source} ({s['cards']} cards) ---")
        print(f"  CER (flat):   {cer_flat:.2%}  ({s['char_errors_flat']} / {s['ref_chars_flat']} chars)")
        print(f"  CER (lines):  {cer_lines:.2%}  ({s['char_errors_lines']} / {s['ref_chars_lines']} chars)")
        print(f"  WER (flat):   {wer_flat:.2%}  ({s['word_errors_flat']} / {s['ref_words_flat']} words)")
        print(f"  WER (lines):  {wer_lines:.2%}  ({s['word_errors_lines']} / {s['ref_words_lines']} words)")

        # Per-card breakdown (up to 50 cards)
        if len(s["card_details"]) <= 50:
            print()
            print(f"  {'Filename':<20} {'CER fl':>7} {'CER ln':>7} {'WER fl':>7} {'WER ln':>7}"
                  f"  {'Ch.e':>4} {'W.e':>4}")
            for d in sorted(s["card_details"], key=lambda x: -x["cer_flat"]):
                print(
                    f"  {d['filename']:<20}"
                    f" {d['cer_flat']:>6.2%}"
                    f" {d['cer_lines']:>6.2%}"
                    f" {d['wer_flat']:>6.2%}"
                    f" {d['wer_lines']:>6.2%}"
                    f"  {d['char_errors_flat']:>3}/{d['ref_chars_flat']:<4}"
                    f" {d['word_errors_flat']:>3}/{d['ref_words_flat']:<3}"
                )

    # Token-level diff for small sets (helps review tokenizer quality)
    all_details = [d for s in stats.values() for d in s["card_details"]]
    if len(all_details) <= 10:
        for variant, tok_ref_key, tok_hyp_key in [
            ("flat", "ref_tokens_flat", "hyp_tokens_flat"),
            ("lines", "ref_tokens_lines", "hyp_tokens_lines"),
        ]:
            print()
            print("=" * 78)
            print(f"TOKEN DIFF — {variant} (ref vs hyp)")
            print("=" * 78)
            for d in all_details:
                print(f"\n  {d['filename']}:")
                ref_t = d[tok_ref_key]
                hyp_t = d[tok_hyp_key]
                max_len = max(len(ref_t), len(hyp_t))
                diffs = []
                for i in range(max_len):
                    r = ref_t[i] if i < len(ref_t) else "---"
                    h = hyp_t[i] if i < len(hyp_t) else "---"
                    if r != h:
                        diffs.append((i, r, h))
                if diffs:
                    print(f"  {'Pos':>4}  {'Reference':<30} {'OCR':<30}")
                    for pos, r, h in diffs:
                        print(f"  {pos:>4}  {r:<30} {h:<30}")
                else:
                    print("  (no word-level differences)")

    # Overall
    t = totals
    cer_flat = t["char_errors_flat"] / t["ref_chars_flat"] if t["ref_chars_flat"] else 0
    cer_lines = t["char_errors_lines"] / t["ref_chars_lines"] if t["ref_chars_lines"] else 0
    wer_flat = t["word_errors_flat"] / t["ref_words_flat"] if t["ref_words_flat"] else 0
    wer_lines = t["word_errors_lines"] / t["ref_words_lines"] if t["ref_words_lines"] else 0

    print()
    print("=" * 78)
    print(f"OVERALL  CER (flat):   {cer_flat:.2%}  ({t['char_errors_flat']} / {t['ref_chars_flat']})")
    print(f"         CER (lines):  {cer_lines:.2%}  ({t['char_errors_lines']} / {t['ref_chars_lines']})")
    print(f"         WER (flat):   {wer_flat:.2%}  ({t['word_errors_flat']} / {t['ref_words_flat']})")
    print(f"         WER (lines):  {wer_lines:.2%}  ({t['word_errors_lines']} / {t['ref_words_lines']})")
    print("=" * 78)


if __name__ == "__main__":
    main()
