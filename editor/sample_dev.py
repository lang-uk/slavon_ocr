#!/usr/bin/env python3
"""Pick a stratified dev sub-sample for cheap prompt-iteration runs.

Strategy: split dev cards into 4 quartiles by baseline CER (computed by
eval_setup.py) and pick N/4 from each quartile with a fixed seed. This
keeps hard cards and easy cards both represented in every sample so we
don't falsely declare a prompt "better" because it happened to see only
easy cards.

Usage:
    python editor/sample_dev.py --seed 0 --size 32
    python editor/sample_dev.py --seed 1 --size 48    # rotate to a fresh sample

Writes editor/samples/sample_<seed>_<size>.json with the chosen keys and
the baseline CER for each.
"""

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
SPLITS_PATH = HERE / "splits.json"
BASELINE_PATH = HERE / "baseline_scores.json"
SAMPLES_DIR = HERE / "samples"


def load():
    splits = json.loads(SPLITS_PATH.read_text())
    baseline = json.loads(BASELINE_PATH.read_text())
    scores = {s["key"]: s for s in baseline["per_card"]}
    dev_keys = set(splits["dev"])
    dev_scored = [scores[k] for k in dev_keys if k in scores]
    return dev_scored


def stratified_sample(dev_scored, size, seed, n_buckets=4):
    # Sort by CER, split into equal-sized buckets
    dev_sorted = sorted(dev_scored, key=lambda s: s["cer_flat"])
    n = len(dev_sorted)
    per_bucket_pick = max(1, size // n_buckets)
    rng = random.Random(seed)

    buckets = []
    for b in range(n_buckets):
        lo = (n * b) // n_buckets
        hi = (n * (b + 1)) // n_buckets
        buckets.append(dev_sorted[lo:hi])

    picked = []
    for b, bucket in enumerate(buckets):
        k = min(per_bucket_pick, len(bucket))
        chosen = rng.sample(bucket, k)
        for c in chosen:
            c2 = dict(c)
            c2["bucket"] = b
            picked.append(c2)

    # Top up if rounding lost a few
    while len(picked) < size:
        candidates = [s for s in dev_sorted if s["key"] not in {p["key"] for p in picked}]
        if not candidates:
            break
        extra = rng.choice(candidates)
        e2 = dict(extra)
        e2["bucket"] = -1  # "top-up" bucket
        picked.append(e2)

    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--size", type=int, default=32)
    ap.add_argument("--buckets", type=int, default=4)
    args = ap.parse_args()

    dev_scored = load()
    if not dev_scored:
        raise SystemExit("No dev cards found — did you run eval_setup.py?")

    picked = stratified_sample(dev_scored, args.size, args.seed, args.buckets)
    picked.sort(key=lambda s: (s.get("bucket", -1), s["cer_flat"]))

    SAMPLES_DIR.mkdir(exist_ok=True)
    out_path = SAMPLES_DIR / f"sample_{args.seed}_{args.size}.json"
    out = {
        "seed": args.seed,
        "size": args.size,
        "n_buckets": args.buckets,
        "from": "dev split",
        "cards": picked,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    print(f"sample: {len(picked)} cards  (wrote {out_path.relative_to(HERE.parent)})")
    for b in range(args.buckets):
        bucket_cards = [p for p in picked if p.get("bucket") == b]
        if not bucket_cards:
            continue
        cers = [c["cer_flat"] for c in bucket_cards]
        print(f"  bucket {b}: n={len(bucket_cards):2}  CER range {min(cers):.1%}..{max(cers):.1%}")
    top_ups = [p for p in picked if p.get("bucket") == -1]
    if top_ups:
        print(f"  top-up: n={len(top_ups)}")


if __name__ == "__main__":
    main()
