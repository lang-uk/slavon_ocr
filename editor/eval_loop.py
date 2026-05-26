#!/usr/bin/env python3
"""Helper for the in-CC OCR eval loop (mirror of pull_loop.py for eval runs).

Two subcommands used by the /ocr_eval_one skill:

    eval_loop.py next --sample <path> --run-id <id>
                      [--source-folder Auto-Color0002_oriented]
        Print the absolute path of the next sample card whose output
        JSON is missing in output/<source>/runs/<run-id>/. Print empty
        when all cards in the sample have outputs.

    eval_loop.py finalize --sample <path> --run-id <id>
                          [--source-folder Auto-Color0002_oriented]
                          [--prompt perestoroha_ocr_preset]
        Write editor/runs/<run-id>.json manifest in the same shape as
        eval_run.py / codex_run.py so score_run.py can consume it.

Durable state is just files on disk: a card is "pending" iff its output
JSON is missing in the run dir. No DB, no flags — survives autocompaction.
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HERE = Path(__file__).parent
RUNS_META_DIR = HERE / "runs"


def _output_path(card: dict, source_folder: str, run_id: str) -> Path:
    filename = card["filename"]
    stem = Path(filename).stem
    return REPO / "output" / source_folder / "runs" / run_id / f"{stem}.json"


def _image_path(card: dict, source_folder: str) -> Path:
    return REPO / "output" / source_folder / card["filename"]


def _looks_like_valid_output(p: Path) -> bool:
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(d, dict):
        return False
    return ("lines" in d) or ("error_type" in d)


def cmd_next(args):
    sample = json.loads(Path(args.sample).read_text())
    cards = sample.get("cards", [])
    if not cards:
        print("", end="")
        return 0
    run_dir = REPO / "output" / args.source_folder / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    for c in cards:
        out = _output_path(c, args.source_folder, args.run_id)
        if not _looks_like_valid_output(out):
            print(str(_image_path(c, args.source_folder)))
            return 0
    print("", end="")
    return 0


def cmd_finalize(args):
    sample_path = Path(args.sample).resolve()
    sample = json.loads(sample_path.read_text())
    cards = sample.get("cards", [])
    records = []
    for c in cards:
        out = _output_path(c, args.source_folder, args.run_id)
        if _looks_like_valid_output(out):
            status = "ok"
        elif out.exists():
            status = "failed"
        else:
            status = "missing"
        records.append({
            "key": c["key"],
            "filename": c["filename"],
            "final_status": status,
            "output_path": str(out.relative_to(REPO)),
        })
    counts = {}
    for r in records:
        counts[r["final_status"]] = counts.get(r["final_status"], 0) + 1
    manifest = {
        "run_id": args.run_id,
        "prompt": args.prompt,
        "source_folder": args.source_folder,
        "sample_path": str(sample_path.relative_to(REPO)) if sample_path.is_relative_to(REPO) else str(sample_path),
        "n_cards": len(cards),
        "model": args.model,
        "cli": "in-cc-agent",
        "reasoning_effort": args.effort,
        "max_parallel": 1,
        "status_counts": counts,
        "records": records,
        "finalized_at": int(time.time()),
    }
    RUNS_META_DIR.mkdir(exist_ok=True)
    out_path = RUNS_META_DIR / f"{args.run_id}.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"manifest: {out_path.relative_to(REPO)} — {counts}")
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    nxt = sub.add_parser("next")
    nxt.add_argument("--sample", required=True)
    nxt.add_argument("--run-id", required=True)
    nxt.add_argument("--source-folder", default="Auto-Color0002_oriented")

    fin = sub.add_parser("finalize")
    fin.add_argument("--sample", required=True)
    fin.add_argument("--run-id", required=True)
    fin.add_argument("--source-folder", default="Auto-Color0002_oriented")
    fin.add_argument("--prompt", default="perestoroha_ocr_preset")
    fin.add_argument("--model", default="claude-opus-4-7")
    fin.add_argument("--effort", default="xhigh")

    args = p.parse_args()
    if args.cmd == "next":
        sys.exit(cmd_next(args))
    elif args.cmd == "finalize":
        sys.exit(cmd_finalize(args))


if __name__ == "__main__":
    main()
