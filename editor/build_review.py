#!/usr/bin/env python3
"""Build an HTML review page showing image + GT + OCR output for every card,
sorted by CER (worst first). Used for manual label auditing.

Usage:
    python editor/build_review.py --run-id prod_all152
    python editor/build_review.py --run-id prod_all152 -o editor/review.html
"""

import argparse
import html
import json
import math
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from eval_setup import clean, flatten, strip_source_line

try:
    import spacy
    from rapidfuzz.distance import Levenshtein
    nlp = spacy.load("uk_core_news_sm")
    HAS_SPACY = True
except Exception:
    from eval_setup import levenshtein as _lev
    HAS_SPACY = False

REPO = Path(__file__).resolve().parent.parent
DB_PATH = Path(__file__).parent / "cards.db"


def tokenize(text):
    if HAS_SPACY:
        text = re.sub(r"-\n", "", text)
        return [t.text for t in nlp(text) if not t.is_space and not t.is_punct]
    return text.split()


def compute_wer(ref_tokens, hyp_tokens):
    if HAS_SPACY:
        return Levenshtein.distance(ref_tokens, hyp_tokens)
    # fallback: pure python
    return _lev(" ".join(ref_tokens), " ".join(hyp_tokens))


def char_dist(a, b):
    if HAS_SPACY:
        return Levenshtein.distance(a, b)
    return _lev(a, b)


def inline_diff_html(ref, hyp):
    """Simple char-level diff highlighting."""
    from eval_setup import levenshtein
    # Use rapidfuzz editops if available
    try:
        from rapidfuzz.distance import Levenshtein as Lev
        ops = Lev.editops(ref, hyp)
    except ImportError:
        return html.escape(ref)

    ref_subs = {}
    ref_dels = set()
    ins_before = {}

    for tag, src, dst in ops:
        if tag == "replace":
            ref_subs[src] = dst
        elif tag == "delete":
            ref_dels.add(src)
        elif tag == "insert":
            ins_before.setdefault(src, []).append(hyp[dst])

    parts = []
    for i, ch in enumerate(ref):
        if i in ins_before:
            for ic in ins_before[i]:
                parts.append(f'<span class="ins">{html.escape(ic)}</span>')
        if i in ref_subs:
            d = ref_subs[i]
            parts.append(
                f'<span class="sub" title="OCR: {html.escape(hyp[d])}">'
                f"{html.escape(ch)}</span>"
            )
        elif i in ref_dels:
            parts.append(f'<span class="del">{html.escape(ch)}</span>')
        else:
            parts.append(html.escape(ch))
    if len(ref) in ins_before:
        for ic in ins_before[len(ref)]:
            parts.append(f'<span class="ins">{html.escape(ic)}</span>')
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("-o", "--output", default="editor/review.html")
    ap.add_argument("--source-folder", default="Auto-Color0002_oriented")
    args = ap.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    proofs = {
        f"{r['folder']}/{r['filename']}": dict(r)
        for r in conn.execute(
            "SELECT * FROM cards WHERE reviewed=1 AND deleted=0 AND lines IS NOT NULL"
        ).fetchall()
    }
    conn.close()

    summary = json.load(open(f"editor/runs/{args.run_id}.summary.json"))
    run_dir = REPO / "output" / args.source_folder / "runs" / args.run_id

    cards = []
    for p in summary["per_card"]:
        key = p["key"]
        fname = key.split("/")[-1]
        proof = proofs.get(key)
        if not proof:
            continue

        # GT
        gt_raw = proof["lines"] or ""
        gt_stripped = strip_source_line(clean(gt_raw), proof["source_reference"])
        gt_flat = flatten(gt_stripped)

        # OCR
        jpath = run_dir / fname.replace(".jpeg", ".json")
        if jpath.exists():
            d = json.loads(jpath.read_text())
            ocr_lines = d.get("lines") or []
            ocr_raw = "\n".join(ocr_lines)
            ocr_stripped = strip_source_line(clean(ocr_raw), proof["source_reference"])
            ocr_flat = flatten(ocr_stripped)
        else:
            ocr_raw = "(missing)"
            ocr_flat = ""

        cer_dist = char_dist(gt_flat, ocr_flat)
        n_chars = len(gt_flat) or 1
        cer = cer_dist / n_chars

        gt_tok = tokenize(gt_flat)
        ocr_tok = tokenize(ocr_flat)
        wer_dist = compute_wer(gt_tok, ocr_tok) if gt_tok else 0
        wer = wer_dist / max(1, len(gt_tok))

        diff_html = inline_diff_html(gt_flat, ocr_flat)

        img_path = f"../output/{args.source_folder}/{fname}"

        cards.append({
            "filename": fname,
            "key": key,
            "img_path": img_path,
            "gt_text": gt_raw,
            "ocr_text": ocr_raw,
            "cer": cer,
            "wer": wer,
            "cer_dist": cer_dist,
            "ref_chars": n_chars,
            "wer_dist": wer_dist,
            "ref_words": len(gt_tok),
            "diff_html": diff_html,
            "source_ref": proof.get("source_reference", ""),
            "card_num": proof.get("card_num_primary", ""),
        })

    cards.sort(key=lambda c: -c["cer"])

    # Distribution stats
    total_chars = sum(c["ref_chars"] for c in cards)
    total_errs = sum(c["cer_dist"] for c in cards)
    total_words = sum(c["ref_words"] for c in cards)
    total_werrs = sum(c["wer_dist"] for c in cards)
    micro_cer = total_errs / total_chars if total_chars else 0
    micro_wer = total_werrs / total_words if total_words else 0

    # Percentile CERs
    sorted_cers = sorted(c["cer"] for c in cards)
    def percentile(arr, p):
        k = (len(arr) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return arr[int(k)]
        return arr[f] * (c - k) + arr[c] * (k - f)

    # Build HTML
    out = [f"""\
<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="utf-8">
<title>OCR Review — {args.run_id}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 1400px; margin: 2em auto; padding: 0 1em; }}
  h1 {{ margin-bottom: 0.2em; }}
  .meta {{ color: #666; font-size: 0.9em; margin-bottom: 1.5em; }}
  .stats {{ background: #f5f5f5; padding: 1em; border-radius: 8px; margin-bottom: 2em; }}
  .stats td {{ padding: 2px 12px; }}
  .card {{ border: 1px solid #ddd; border-radius: 8px; margin: 1.5em 0; overflow: hidden; }}
  .card-header {{ background: #f8f8f8; padding: 0.6em 1em; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }}
  .card-header .fname {{ font-weight: bold; font-size: 1.1em; }}
  .card-header .cer {{ font-size: 1.1em; }}
  .cer-good {{ color: #2e7d32; }}
  .cer-ok {{ color: #f57f17; }}
  .cer-bad {{ color: #c62828; }}
  .card-body {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; }}
  .card-body .img-col {{ padding: 0.5em; border-right: 1px solid #eee; }}
  .card-body .text-col {{ padding: 0.8em; }}
  .card-body img {{ max-width: 100%; height: auto; }}
  .text-col h4 {{ margin: 0 0 0.3em 0; color: #555; font-size: 0.85em; text-transform: uppercase; }}
  .text-col pre {{ font-family: serif; font-size: 1em; line-height: 1.5; white-space: pre-wrap; word-break: break-word; margin: 0 0 0.8em 0; }}
  .diff {{ background: #fafafa; padding: 0.5em; border-radius: 4px; margin-top: 0.3em; }}
  .sub {{ background: #ffe0b2; border-bottom: 2px solid #f57c00; cursor: help; }}
  .del {{ background: #ffcdd2; text-decoration: line-through; }}
  .ins {{ background: #c8e6c9; }}
</style>
</head>
<body>
<h1>OCR Review — {html.escape(args.run_id)}</h1>
<p class="meta">{len(cards)} cards &middot; sorted by CER (worst first)</p>

<div class="stats">
<table>
<tr><td><b>Micro CER (flat)</b></td><td>{micro_cer:.2%}</td><td>({total_errs}/{total_chars} chars)</td></tr>
<tr><td><b>Micro WER (flat)</b></td><td>{micro_wer:.2%}</td><td>({total_werrs}/{total_words} words)</td></tr>
<tr><td colspan="3" style="padding-top:8px"><b>Per-card CER distribution:</b></td></tr>
<tr><td>Median</td><td>{percentile(sorted_cers, 50):.2%}</td><td></td></tr>
<tr><td>P25 / P75</td><td>{percentile(sorted_cers, 25):.2%} / {percentile(sorted_cers, 75):.2%}</td><td></td></tr>
<tr><td>P10 / P90</td><td>{percentile(sorted_cers, 10):.2%} / {percentile(sorted_cers, 90):.2%}</td><td></td></tr>
<tr><td>Min / Max</td><td>{sorted_cers[0]:.2%} / {sorted_cers[-1]:.2%}</td><td></td></tr>
<tr><td>Zero-error cards</td><td>{sum(1 for c in sorted_cers if c == 0)}</td><td></td></tr>
</table>
</div>
"""]

    for i, c in enumerate(cards, 1):
        cer_pct = c["cer"]
        cls = "cer-good" if cer_pct < 0.03 else ("cer-ok" if cer_pct < 0.08 else "cer-bad")
        out.append(f"""
<div class="card" id="{html.escape(c['filename'])}">
  <div class="card-header">
    <span class="fname">#{i} — {html.escape(c['filename'])}</span>
    <span>card #{html.escape(str(c['card_num']))}</span>
    <span class="cer {cls}">CER {cer_pct:.1%} &middot; WER {c['wer']:.1%} &middot; {c['cer_dist']} errs / {c['ref_chars']} chars</span>
  </div>
  <div class="card-body">
    <div class="img-col">
      <img src="{html.escape(c['img_path'])}" alt="{html.escape(c['filename'])}" loading="lazy">
    </div>
    <div class="text-col">
      <h4>Ground Truth</h4>
      <pre>{html.escape(c['gt_text'])}</pre>
      <h4>OCR Output</h4>
      <pre>{html.escape(c['ocr_text'])}</pre>
      <h4>Diff (GT annotated: <span class="sub">sub</span> <span class="del">del</span> <span class="ins">ins</span>)</h4>
      <pre class="diff">{c['diff_html']}</pre>
    </div>
  </div>
</div>
""")

    out.append("</body></html>")

    outpath = Path(args.output)
    outpath.write_text("".join(out), encoding="utf-8")
    print(f"wrote {outpath} ({len(cards)} cards)")

    # Print distribution to console too
    print(f"\nCER/WER distribution:")
    print(f"  micro CER: {micro_cer:.2%}  ({total_errs}/{total_chars})")
    print(f"  micro WER: {micro_wer:.2%}  ({total_werrs}/{total_words})")
    print(f"  median CER: {percentile(sorted_cers, 50):.2%}")
    print(f"  P25/P75:    {percentile(sorted_cers, 25):.2%} / {percentile(sorted_cers, 75):.2%}")
    print(f"  P10/P90:    {percentile(sorted_cers, 10):.2%} / {percentile(sorted_cers, 90):.2%}")
    print(f"  min/max:    {sorted_cers[0]:.2%} / {sorted_cers[-1]:.2%}")
    print(f"  zero-error: {sum(1 for c in sorted_cers if c == 0)}")
    print(f"  <2%:        {sum(1 for c in sorted_cers if c < 0.02)}")
    print(f"  <5%:        {sum(1 for c in sorted_cers if c < 0.05)}")
    print(f"  <10%:       {sum(1 for c in sorted_cers if c < 0.10)}")
    print(f"  >=10%:      {sum(1 for c in sorted_cers if c >= 0.10)}")


if __name__ == "__main__":
    main()
