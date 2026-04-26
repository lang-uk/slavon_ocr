#!/usr/bin/env python3
"""Tabulate and diff prompt-iteration runs.

By default, the baseline is the frozen `original_json` already stored in
cards.db — no re-run needed. Filter it to whichever cards a run touched
(using that run's manifest) and compute per-sample micro-CER for a
fair comparison.

Specify any number of run ids as positional args. Optionally a different
baseline run with --baseline <id>.

Usage:
    python editor/compare_runs.py v1
    python editor/compare_runs.py v1 v2 v3
    python editor/compare_runs.py v1 v2 --baseline v0

Optionally counts prompt tokens via Anthropic's count_tokens API if
`anthropic` is installed and ANTHROPIC_API_KEY is set. Pass --count-tokens
to enable.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from eval_setup import (
    clean,
    flatten,
    strip_source_line,
    extract_ocr_lines,
    levenshtein,
)

REPO = Path(__file__).resolve().parent.parent
HERE = Path(__file__).parent
RUNS_META_DIR = HERE / "runs"
BASELINE_PATH = HERE / "baseline_scores.json"
PROMPTS_DIR = REPO / ".claude" / "commands"


def load_manifest(run_id):
    p = RUNS_META_DIR / f"{run_id}.json"
    if not p.exists():
        raise SystemExit(f"No manifest for run {run_id!r}: {p}")
    return json.loads(p.read_text())


def load_summary(run_id):
    p = RUNS_META_DIR / f"{run_id}.summary.json"
    if not p.exists():
        raise SystemExit(f"No summary for run {run_id!r}. Run score_run.py first.")
    return json.loads(p.read_text())


def synthesize_baseline_for_cards(card_keys):
    """Compute a micro-CER for the DB baseline restricted to a card set."""
    baseline = json.loads(BASELINE_PATH.read_text())
    per_card = {s["key"]: s for s in baseline["per_card"]}

    picked = []
    total_chars = 0
    total_errors = 0
    for k in card_keys:
        if k not in per_card:
            continue
        s = per_card[k]
        picked.append(s)
        total_chars += s["ref_chars"]
        total_errors += s["errors"]
    micro_cer = total_errors / total_chars if total_chars else 0.0
    return {
        "run_id": "baseline(db)",
        "prompt": "ocr (frozen original_json)",
        "n_scored": len(picked),
        "total_ref_chars": total_chars,
        "total_errors": total_errors,
        "micro_cer_flat": micro_cer,
    }


def count_prompt_tokens(prompt_name):
    """Use Anthropic's count_tokens API if possible; return None otherwise."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    p = PROMPTS_DIR / f"{prompt_name}.md"
    if not p.exists():
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.count_tokens(
            model="claude-opus-4-5",
            messages=[{"role": "user", "content": p.read_text()}],
        )
        return resp.input_tokens
    except Exception as e:
        print(f"[warn] token count failed for {prompt_name}: {e}", file=sys.stderr)
        return None


def prompt_char_count(prompt_name):
    p = PROMPTS_DIR / f"{prompt_name}.md"
    return len(p.read_text()) if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_ids", nargs="+", help="Run ids to tabulate")
    ap.add_argument("--baseline", default=None,
                    help="Use another run as baseline instead of the DB's frozen OCR")
    ap.add_argument("--count-tokens", action="store_true",
                    help="Query Anthropic token counter for each prompt")
    args = ap.parse_args()

    summaries = [load_summary(r) for r in args.run_ids]

    # Pick a card-set to compare across: use the first run's scored keys
    # (all runs on the same sample should share the same set).
    first = summaries[0]
    card_keys = [p["key"] for p in first["per_card"]]

    if args.baseline:
        baseline_summary = load_summary(args.baseline)
    else:
        baseline_summary = synthesize_baseline_for_cards(card_keys)

    # --- Side-by-side table ---
    print("=" * 88)
    print(f"{'run':20}  {'prompt':15}  {'cards':>5}  {'chars':>6}  {'errors':>6}  {'CER':>7}  {'Δ':>7}")
    print("-" * 88)

    def row(name, prompt, n, chars, errs, cer, delta):
        delta_s = f"{delta*100:+.2f}pp" if delta is not None else "—"
        print(f"{name:20}  {prompt[:15]:15}  {n:>5}  {chars:>6}  {errs:>6}  {cer:>6.2%}  {delta_s:>7}")

    row(baseline_summary["run_id"],
        baseline_summary.get("prompt", "?"),
        baseline_summary["n_scored"],
        baseline_summary["total_ref_chars"],
        baseline_summary["total_errors"],
        baseline_summary["micro_cer_flat"],
        None)
    for s in summaries:
        delta = s["micro_cer_flat"] - baseline_summary["micro_cer_flat"]
        row(s["run_id"], s.get("prompt", "?"),
            s["n_scored"], s["total_ref_chars"], s["total_errors"],
            s["micro_cer_flat"], delta)
    print("=" * 88)

    # --- Prompt size ---
    print("\nPrompt size:")
    print(f"  {'prompt':20}  {'chars':>6}  {'tokens':>7}")
    seen = set()
    for s in summaries:
        p = s.get("prompt")
        if not p or p in seen:
            continue
        seen.add(p)
        cc = prompt_char_count(p) or "?"
        tc = count_prompt_tokens(p) if args.count_tokens else None
        tc_s = str(tc) if tc is not None else ("—" if args.count_tokens else "(skip)")
        print(f"  {p:20}  {str(cc):>6}  {tc_s:>7}")

    # --- Top substitutions diff vs baseline ---
    # Only works if the baseline is another run (has top_substitutions),
    # not the DB-synthesized baseline.
    if args.baseline and "top_substitutions" in baseline_summary:
        base_subs = {(x["ref"], x["hyp"]): x["count"]
                     for x in baseline_summary["top_substitutions"]}
        for s in summaries:
            run_subs = {(x["ref"], x["hyp"]): x["count"]
                        for x in s.get("top_substitutions", [])}
            all_keys = set(base_subs) | set(run_subs)
            diffs = []
            for k in all_keys:
                b, r = base_subs.get(k, 0), run_subs.get(k, 0)
                if b != r:
                    diffs.append((k, r - b, b, r))
            diffs.sort(key=lambda d: abs(d[1]), reverse=True)
            if not diffs:
                continue
            print(f"\nSubstitution deltas — {s['run_id']} vs {baseline_summary['run_id']}:")
            for (rc, hc), d, b, r in diffs[:10]:
                sign = "+" if d > 0 else ""
                print(f"  {rc!r:>4} -> {hc!r:<4}  {sign}{d:+3}  (baseline {b}, run {r})")


if __name__ == "__main__":
    main()
