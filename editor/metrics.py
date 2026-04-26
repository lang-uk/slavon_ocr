#!/usr/bin/env python3
"""Targeted-metric comparison across runs.

Aggregate CER on 32-card samples has a ~1.85pp noise floor (measured by
running the same prompt twice), which is too noisy for fine-grained prompt
iteration. Targeted per-error-class metrics are much more stable and
sensitive — the є/е count differs by ±1 between two runs of the same prompt,
whereas total error count differs by ~80.

This script tabulates specific substitution/insertion/deletion classes
across runs so you can see exactly which error classes a prompt change
fixed and which it broke, without being drowned in noise.

Usage:
    python editor/metrics.py baseline_rot baseline_rot_2 v1 ee1 perest1
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = HERE / "runs"

# Substitution pairs worth tracking for Пересторога. Each entry:
#   (ref_char, hyp_char, label)
# Ordered by expected frequency in Пересторога baseline.
TRACKED_SUBS = [
    ("є", "е",  "є→е"),
    ("е", "є",  "е→є"),
    ("ы", "и",  "ы→и"),
    ("я", "ѧ",  "я→ѧ"),
    ("ъ", "ь",  "ъ→ь"),
    ("ь", "ъ",  "ь→ъ"),
    ("ѣ", "ъ",  "ѣ→ъ"),
    ("ѣ", "і",  "ѣ→і"),
    ("ѣ", "е",  "ѣ→е"),
    ("і", "ї",  "і→ї"),
    ("і", "и",  "і→и"),
    ("у", "ү",  "у→ү"),
]

# Characters that should never appear in Пересторога transcriptions
# (Кройника-only). Count as a "banned letter" budget.
BANNED_HYP_CHARS = set("ѫѧӕїѹωώѠѯѵsѕ") | {"\u033e", "\u0301", "\u0483"}


def load_summary(run_id: str):
    p = RUNS / f"{run_id}.summary.json"
    if not p.exists():
        raise SystemExit(f"No summary for {run_id}: {p}")
    return json.loads(p.read_text())


def sub_count(summary, ref, hyp):
    for s in summary.get("top_substitutions", []):
        if s["ref"] == ref and s["hyp"] == hyp:
            return s["count"]
    return 0


def banned_insertions_count(summary):
    """Sum of insertion counts whose char is a banned Кройника letter."""
    total = 0
    for entry in summary.get("top_insertions", []):
        if entry["char"] in BANNED_HYP_CHARS:
            total += entry["count"]
    return total


def banned_sub_count(summary):
    """Substitutions whose hyp char is a banned Кройника letter."""
    total = 0
    for entry in summary.get("top_substitutions", []):
        if entry["hyp"] in BANNED_HYP_CHARS:
            total += entry["count"]
    return total


def banned_total(summary):
    return banned_insertions_count(summary) + banned_sub_count(summary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_ids", nargs="+")
    args = ap.parse_args()

    summaries = [(rid, load_summary(rid)) for rid in args.run_ids]

    # --- Aggregate CER table ---
    print("=" * 72)
    print(f"{'run':20} {'CER':>7} {'errors':>7} {'banned':>7}")
    print("-" * 72)
    for rid, s in summaries:
        cer = s["micro_cer_flat"]
        errs = s["total_errors"]
        banned = banned_total(s)
        print(f"{rid:20} {cer:>6.2%} {errs:>7} {banned:>7}")
    print()

    # --- Targeted substitution table ---
    header = f"{'metric':10}" + "".join(f"{rid[:10]:>11}" for rid, _ in summaries)
    print("Targeted substitutions (count per run):")
    print(header)
    print("-" * len(header))
    for ref, hyp, label in TRACKED_SUBS:
        row = f"{label:10}"
        for _, s in summaries:
            n = sub_count(s, ref, hyp)
            row += f"{n:>11}"
        print(row)

    # --- Derived: є/е total ---
    print()
    total_ee_row = f"{'є/е total':10}"
    for _, s in summaries:
        total_ee_row += f"{sub_count(s,'є','е')+sub_count(s,'е','є'):>11}"
    print(total_ee_row)

    # --- Best/worst per-metric ---
    print()
    print("Per-metric winners (lowest count across runs):")
    for ref, hyp, label in TRACKED_SUBS:
        counts = [(rid, sub_count(s, ref, hyp)) for rid, s in summaries]
        counts.sort(key=lambda x: x[1])
        best_rid, best_c = counts[0]
        worst_rid, worst_c = counts[-1]
        if best_c != worst_c:
            print(f"  {label:8}  best={best_rid}({best_c})  worst={worst_rid}({worst_c})")

    # --- Banned-letter budget ---
    print()
    print("Banned-letter budget (Пересторога should have zero):")
    for rid, s in summaries:
        bi = banned_insertions_count(s)
        bs = banned_sub_count(s)
        print(f"  {rid:20}  subs={bs:>3}  ins={bi:>3}  total={bi+bs:>3}")


if __name__ == "__main__":
    main()
