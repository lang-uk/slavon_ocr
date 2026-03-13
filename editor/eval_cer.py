#!/usr/bin/env python3
"""Compute CER and WER between original OCR and proofread text for reviewed cards.

Both CER and WER are reported in two variants:
  - flat:  lines concatenated into one string, line breaks ignored
  - lines: line breaks preserved, hyphenated words rejoined across lines

WER uses spacy's Ukrainian tokenizer (uk_core_news_sm).
Whitespace and punctuation tokens are excluded from word counts.

Produces an HTML report with character-level diffs in editor/char_diffs.html.
"""

import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import spacy
from rapidfuzz.distance import Levenshtein

from db import get_db

nlp = spacy.load("uk_core_news_sm")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _normalize_dashes(s):
    """Collapse spaces around dashes/en-dashes/em-dashes into a plain hyphen."""
    return re.sub(r"\s*[-\u2013\u2014]\s*", "-", s)


def strip_source_line(text, row):
    """Remove the last line if it contains the source reference metadata.

    Some OCR runs included the source line (e.g. 'Львів, 1605-1606, Перест. 28.')
    in the transcription; others parsed it into structured fields and excluded it.
    Reviewers sometimes removed it. To avoid penalizing this editorial mismatch,
    we strip it from both sides before comparison.

    Uses dash-normalized comparison to handle variations like
    '1605 - 1606' vs '1605-1606' or '34 - 35' vs '34-35'.
    """
    ref = (row["source_reference"] or "").strip().rstrip(".")
    if not ref:
        return text

    lines = text.split("\n")
    if not lines:
        return text

    last = _normalize_dashes(lines[-1].strip()).lower()
    ref_clean = _normalize_dashes(ref).lower()
    if ref_clean in last:
        return "\n".join(lines[:-1]).strip()

    return text


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


def render_inline_diff(ref, hyp):
    """Return HTML with ref text annotated: substitutions in orange, deletions in
    red (strikethrough), insertions in green."""
    ops = Levenshtein.editops(ref, hyp)
    # Build sets for quick lookup
    ref_subs = {}   # src_pos -> dest_pos  (replace)
    ref_dels = set()  # src_pos  (delete)
    hyp_ins = {}    # dest_pos -> char  (insert) — keyed by *dest* pos

    # We also need to know *where* insertions go relative to ref positions.
    # An insert at (src_pos, dest_pos) means the char hyp[dest_pos] is inserted
    # before ref[src_pos].
    ins_before = defaultdict(list)  # src_pos -> [hyp chars inserted before it]

    for tag, src_pos, dest_pos in ops:
        if tag == "replace":
            ref_subs[src_pos] = dest_pos
        elif tag == "delete":
            ref_dels.add(src_pos)
        elif tag == "insert":
            ins_before[src_pos].append(hyp[dest_pos])

    parts = []
    for i, ch in enumerate(ref):
        # Any insertions before this position?
        if i in ins_before:
            for ic in ins_before[i]:
                parts.append(f'<span class="ins">{html.escape(ic)}</span>')
        if i in ref_subs:
            dest = ref_subs[i]
            parts.append(
                f'<span class="sub" title="OCR: {html.escape(hyp[dest])}">'
                f'{html.escape(ch)}</span>'
            )
        elif i in ref_dels:
            parts.append(f'<span class="del">{html.escape(ch)}</span>')
        else:
            parts.append(html.escape(ch))

    # Insertions after the last ref char
    if len(ref) in ins_before:
        for ic in ins_before[len(ref)]:
            parts.append(f'<span class="ins">{html.escape(ic)}</span>')

    return "".join(parts)


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

    # Compute metrics for both original case and lowercased
    case_variants = [
        ("original", lambda t: t),
        ("lowercased", lambda t: t.lower()),
    ]

    all_results = {}  # variant_name -> {stats, totals}

    for variant_name, transform in case_variants:
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

            # Clean \r from both, strip source metadata line
            ocr_clean = strip_source_line(clean(ocr_raw), row)
            proof_clean = strip_source_line(clean(proof_raw), row)

            if not ocr_clean and not proof_clean:
                continue

            # Apply case transform
            ocr_clean = transform(ocr_clean)
            proof_clean = transform(proof_clean)

            source = classify_source(row)
            s = stats[source]
            s["cards"] += 1

            # --- CER (flat): no line breaks ---
            proof_flat = flatten(proof_clean)
            ocr_flat = flatten(ocr_clean)
            char_dist_flat = Levenshtein.distance(proof_flat, ocr_flat)
            ref_chars_flat = len(proof_flat) or 1

            # --- CER (lines): line breaks preserved ---
            char_dist_lines = Levenshtein.distance(proof_clean, ocr_clean)
            ref_chars_lines = len(proof_clean) or 1

            # --- WER (flat) ---
            ref_tokens_flat = tokenize(proof_flat, do_rejoin_hyphens=False)
            hyp_tokens_flat = tokenize(ocr_flat, do_rejoin_hyphens=False)
            word_dist_flat = Levenshtein.distance(ref_tokens_flat, hyp_tokens_flat)
            n_ref_words_flat = len(ref_tokens_flat) or 1

            # --- WER (lines) ---
            ref_tokens_lines = tokenize(proof_clean, do_rejoin_hyphens=True)
            hyp_tokens_lines = tokenize(ocr_clean, do_rejoin_hyphens=True)
            word_dist_lines = Levenshtein.distance(ref_tokens_lines, hyp_tokens_lines)
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
                "folder": row["folder"],
                "cer_flat": char_dist_flat / ref_chars_flat,
                "cer_lines": char_dist_lines / ref_chars_lines,
                "wer_flat": word_dist_flat / n_ref_words_flat,
                "wer_lines": word_dist_lines / n_ref_words_lines,
                "char_errors_flat": char_dist_flat,
                "ref_chars_flat": ref_chars_flat,
                "word_errors_flat": word_dist_flat,
                "ref_words_flat": n_ref_words_flat,
            })

        all_results[variant_name] = stats

    # --- Print report ---
    print("=" * 78)
    print("OCR EVALUATION REPORT")
    print(f"Reviewed cards: {len(rows)}")
    print("Reference: human-proofread | Hypothesis: original OCR")
    print("Tokenizer: spacy uk_core_news_sm (hyphens rejoined, punct excluded)")
    print("Source metadata lines stripped from both sides before comparison")
    print("=" * 78)

    for variant_name, stats in all_results.items():
        print(f"\n{'*' * 78}")
        print(f"  CASE: {variant_name}")
        print(f"{'*' * 78}")

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

            # Per-card breakdown (only for original case, up to 50 cards)
            if variant_name == "original" and len(s["card_details"]) <= 50:
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

        # Overall for this variant
        t = totals
        cer_flat = t["char_errors_flat"] / t["ref_chars_flat"] if t["ref_chars_flat"] else 0
        cer_lines = t["char_errors_lines"] / t["ref_chars_lines"] if t["ref_chars_lines"] else 0
        wer_flat = t["word_errors_flat"] / t["ref_words_flat"] if t["ref_words_flat"] else 0
        wer_lines = t["word_errors_lines"] / t["ref_words_lines"] if t["ref_words_lines"] else 0

        print()
        print(f"  OVERALL ({variant_name})")
        print(f"    CER (flat):   {cer_flat:.2%}  ({t['char_errors_flat']} / {t['ref_chars_flat']})")
        print(f"    CER (lines):  {cer_lines:.2%}  ({t['char_errors_lines']} / {t['ref_chars_lines']})")
        print(f"    WER (flat):   {wer_flat:.2%}  ({t['word_errors_flat']} / {t['ref_words_flat']})")
        print(f"    WER (lines):  {wer_lines:.2%}  ({t['word_errors_lines']} / {t['ref_words_lines']})")

    # --- Character-level diff collection ---
    substitutions = Counter()   # (ref_char, ocr_char) -> count
    insertions = Counter()      # ocr_char -> count  (extra chars in OCR)
    deletions = Counter()       # ref_char -> count  (missing from OCR)
    per_card_diffs = []         # [{filename, folder, cer, errors, ref_text, inline_diff_html}, ...]

    for row in rows:
        ocr_raw = extract_ocr_text(row["original_json"])
        proof_raw = row["lines"] or ""

        ocr_clean = strip_source_line(clean(ocr_raw), row)
        proof_clean = strip_source_line(clean(proof_raw), row)
        if not ocr_clean and not proof_clean:
            continue

        # Use flat (no linebreaks) so we focus on character errors, not formatting
        ref_text = flatten(proof_clean)
        hyp_text = flatten(ocr_clean)

        ops = Levenshtein.editops(ref_text, hyp_text)
        n_errors = len(ops)
        cer = n_errors / (len(ref_text) or 1)

        for tag, src_pos, dest_pos in ops:
            if tag == "replace":
                substitutions[(ref_text[src_pos], hyp_text[dest_pos])] += 1
            elif tag == "insert":
                insertions[hyp_text[dest_pos]] += 1
            elif tag == "delete":
                deletions[ref_text[src_pos]] += 1

        if n_errors > 0:
            diff_html = render_inline_diff(ref_text, hyp_text)
            per_card_diffs.append({
                "filename": row["filename"],
                "folder": row["folder"],
                "cer": cer,
                "errors": n_errors,
                "ref_len": len(ref_text),
                "ref_text": ref_text,
                "ocr_text": hyp_text,
                "inline_diff_html": diff_html,
            })

    per_card_diffs.sort(key=lambda d: -d["cer"])

    # --- Generate HTML report ---
    html_parts = [HTML_HEAD]

    # Summary stats
    orig_stats = all_results["original"]
    t = defaultdict(int)
    for s in orig_stats.values():
        for k in ("ref_chars_flat", "char_errors_flat", "ref_words_flat", "word_errors_flat"):
            t[k] += s[k]
    overall_cer = t["char_errors_flat"] / t["ref_chars_flat"] if t["ref_chars_flat"] else 0
    overall_wer = t["word_errors_flat"] / t["ref_words_flat"] if t["ref_words_flat"] else 0

    html_parts.append(f"""
<h1>OCR Error Analysis</h1>
<p class="meta">{len(rows)} reviewed cards &middot;
CER {overall_cer:.2%} &middot; WER {overall_wer:.2%}</p>
""")

    # Worst cards table
    html_parts.append("""
<h2>Cards by error rate (worst first)</h2>
<table>
<tr><th>#</th><th>Filename</th><th>Folder</th><th>CER</th><th>Errors</th><th>Chars</th></tr>
""")
    for i, d in enumerate(per_card_diffs, 1):
        cer_pct = f"{d['cer']:.1%}"
        cls = ' class="worst"' if d["cer"] > 0.20 else ""
        html_parts.append(
            f'<tr{cls}><td>{i}</td><td><a href="#{d["folder"]}/{d["filename"]}">'
            f'{d["filename"]}</a></td>'
            f'<td>{html.escape(d["folder"])}</td>'
            f"<td>{cer_pct}</td><td>{d['errors']}</td><td>{d['ref_len']}</td></tr>\n"
        )
    html_parts.append("</table>\n")

    # Substitution table
    html_parts.append(f"""
<h2>Substitutions ({sum(substitutions.values())} total, {len(substitutions)} types)</h2>
<table>
<tr><th>Reference</th><th>OCR</th><th>Count</th><th>Codepoints</th></tr>
""")
    for (rc, hc), cnt in substitutions.most_common():
        html_parts.append(
            f"<tr><td class=\"char\">{html.escape(rc)}</td>"
            f"<td class=\"char\">{html.escape(hc)}</td>"
            f"<td>{cnt}</td>"
            f"<td>U+{ord(rc):04X} &rarr; U+{ord(hc):04X}</td></tr>\n"
        )
    html_parts.append("</table>\n")

    # Insertions table
    html_parts.append(f"""
<h2>Insertions — extra in OCR ({sum(insertions.values())} total)</h2>
<table>
<tr><th>Char</th><th>Count</th><th>Codepoint</th></tr>
""")
    for ch, cnt in insertions.most_common():
        html_parts.append(
            f"<tr><td class=\"char\">{html.escape(ch)}</td>"
            f"<td>{cnt}</td><td>U+{ord(ch):04X}</td></tr>\n"
        )
    html_parts.append("</table>\n")

    # Deletions table
    html_parts.append(f"""
<h2>Deletions — missing from OCR ({sum(deletions.values())} total)</h2>
<table>
<tr><th>Char</th><th>Count</th><th>Codepoint</th></tr>
""")
    for ch, cnt in deletions.most_common():
        html_parts.append(
            f"<tr><td class=\"char\">{html.escape(ch)}</td>"
            f"<td>{cnt}</td><td>U+{ord(ch):04X}</td></tr>\n"
        )
    html_parts.append("</table>\n")

    # Per-card inline diffs
    html_parts.append("<h2>Per-card character diffs</h2>\n")
    html_parts.append("<p>Legend: "
                       "<span class=\"sub\">substitution</span> (hover for OCR char), "
                       "<span class=\"del\">deletion</span> (in ref but not OCR), "
                       "<span class=\"ins\">insertion</span> (in OCR but not ref)</p>\n")

    for d in per_card_diffs:
        anchor = f'{d["folder"]}/{d["filename"]}'
        html_parts.append(
            f'<div class="card" id="{html.escape(anchor)}">'
            f'<h3>{html.escape(d["filename"])} '
            f'<span class="meta">({d["folder"]}, CER {d["cer"]:.1%}, '
            f'{d["errors"]} errors / {d["ref_len"]} chars)</span></h3>'
            f'<pre class="diff">{d["inline_diff_html"]}</pre>'
            f"</div>\n"
        )

    html_parts.append("</body></html>")

    diff_path = Path(__file__).parent / "char_diffs.html"
    diff_path.write_text("".join(html_parts), encoding="utf-8")

    # Print character diff summary to console
    print()
    print("=" * 78)
    print("CHARACTER-LEVEL ERROR ANALYSIS")
    print(f"Saved HTML report to: {diff_path}")
    print("=" * 78)

    if per_card_diffs:
        print(f"\nWorst cards by CER (>{20}%):")
        for d in per_card_diffs:
            if d["cer"] <= 0.20:
                break
            print(f"  {d['filename']:<20} CER {d['cer']:>6.1%}  "
                  f"({d['errors']} errors / {d['ref_len']} chars)  [{d['folder']}]")

    if substitutions:
        print(f"\nTop substitutions (ref -> ocr)  [{sum(substitutions.values())} total]:")
        for (rc, hc), cnt in substitutions.most_common(20):
            print(f"  '{rc}' (U+{ord(rc):04X}) -> '{hc}' (U+{ord(hc):04X})  x{cnt}")

    # Summary comparison table
    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  {'Metric':<16} {'Original':>10} {'Lowercased':>12} {'Diff':>8}")
    print(f"  {'-'*16} {'-'*10} {'-'*12} {'-'*8}")
    for metric in ("CER (flat)", "CER (lines)", "WER (flat)", "WER (lines)"):
        key_map = {
            "CER (flat)": ("char_errors_flat", "ref_chars_flat"),
            "CER (lines)": ("char_errors_lines", "ref_chars_lines"),
            "WER (flat)": ("word_errors_flat", "ref_words_flat"),
            "WER (lines)": ("word_errors_lines", "ref_words_lines"),
        }
        err_k, ref_k = key_map[metric]
        vals = []
        for vn in ("original", "lowercased"):
            t = defaultdict(int)
            for s in all_results[vn].values():
                t[err_k] += s[err_k]
                t[ref_k] += s[ref_k]
            vals.append(t[err_k] / t[ref_k] if t[ref_k] else 0)
        diff = vals[1] - vals[0]
        print(f"  {metric:<16} {vals[0]:>9.2%} {vals[1]:>11.2%} {diff:>+7.2%}")


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_HEAD = """\
<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<title>OCR Character-Level Error Analysis</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; }
  h1 { margin-bottom: 0.2em; }
  .meta { color: #666; font-size: 0.9em; }
  table { border-collapse: collapse; margin: 1em 0; }
  th, td { border: 1px solid #ccc; padding: 4px 10px; text-align: left; }
  th { background: #f5f5f5; position: sticky; top: 0; }
  tr.worst { background: #fff0f0; }
  .char { font-size: 1.3em; font-family: serif; }
  .card { margin: 1.5em 0; border-top: 1px solid #ddd; padding-top: 0.5em; }
  .card h3 { margin: 0.3em 0; }
  pre.diff { font-family: serif; font-size: 1.1em; line-height: 1.6;
             white-space: pre-wrap; word-break: break-word;
             background: #fafafa; padding: 0.8em; border-radius: 4px; }
  .sub { background: #ffe0b2; border-bottom: 2px solid #f57c00; cursor: help; }
  .del { background: #ffcdd2; text-decoration: line-through; }
  .ins { background: #c8e6c9; }
</style>
</head>
<body>
"""


if __name__ == "__main__":
    main()
