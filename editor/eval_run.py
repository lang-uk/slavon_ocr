#!/usr/bin/env python3
"""Run a prompt variant against a dev sample, collecting outputs in isolation.

Per run, we create a scratch directory:
    output/<source_folder>/runs/<run-id>/
populated with symlinks to the canonical (oriented) card images. We then
invoke `claude -p /<prompt-name> @<symlink>` once per card; the ocr prompt
saves its output JSON next to the image, which in this scratch dir means
our run directory — giving us perfect isolation between prompt variants.

Thinking is enabled with a budget. If the first attempt produces no valid
JSON (timeout, thinking budget exhausted, parse error), we retry that card
once with thinking disabled. Either outcome is recorded in the manifest.

Usage:
    python editor/eval_run.py --prompt ocr --run-id baseline --sample editor/samples/sample_0_32.json
    python editor/eval_run.py --prompt ocr_new --run-id v1 --sample editor/samples/sample_0_32.json
    python editor/eval_run.py ... --parallel 4      # run 4 claude processes concurrently
    python editor/eval_run.py ... --force           # overwrite existing run outputs
    python editor/eval_run.py ... --source-folder Auto-Color0002_oriented

Outputs:
  - output/<source>/runs/<run-id>/*.json   Claude's raw outputs
  - editor/runs/<run-id>/manifest.json     card list + per-card status
"""

import argparse
import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HERE = Path(__file__).parent
RUNS_META_DIR = HERE / "runs"


def ensure_symlink(src: Path, dst: Path):
    """Create dst as a symlink to src (absolute). Idempotent."""
    src = src.resolve()
    if dst.exists() or dst.is_symlink():
        try:
            if Path(os.readlink(dst)).resolve() == src:
                return
        except OSError:
            pass
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.symlink_to(src)


def looks_like_valid_output(path: Path) -> bool:
    """Did Claude write a parseable JSON with either lines or error_type?"""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    # Either a transcription (lines list) or an error marker (error_type)
    return ("lines" in data) or ("error_type" in data)


def run_claude_once(image_symlink: Path, prompt_name: str, *,
                    thinking: bool, max_tokens: int, max_thinking_tokens: int,
                    timeout_s: int,
                    model: str | None = None,
                    effort: str | None = None,
                    ref_image: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_tokens)
    if thinking:
        env.pop("CLAUDE_CODE_DISABLE_THINKING", None)
        env["MAX_THINKING_TOKENS"] = str(max_thinking_tokens)
        env["CLAUDE_CODE_MAX_THINKING_TOKENS"] = str(max_thinking_tokens)
    else:
        env["CLAUDE_CODE_DISABLE_THINKING"] = "1"
        env["MAX_THINKING_TOKENS"] = "0"
        env["CLAUDE_CODE_MAX_THINKING_TOKENS"] = "0"
    cmd = ["claude", "--allowedTools", "Write"]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    ref_part = f"@{ref_image} " if ref_image else ""
    cmd += ["-p", f"/{prompt_name} {ref_part}@{image_symlink}"]
    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def process_card(card_key: str, *, source_folder: str, prompt_name: str,
                 run_id: str, max_tokens: int, max_thinking_tokens: int,
                 timeout_s: int, force: bool,
                 model: str | None = None,
                 effort: str | None = None,
                 ref_image: Path | None = None) -> dict:
    """Run one card. Returns a status record."""
    folder, filename = card_key.split("/", 1)
    original_image = REPO / "output" / source_folder / filename
    run_dir = REPO / "output" / source_folder / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    image_symlink = run_dir / filename
    output_json = run_dir / (Path(filename).stem + ".json")

    record = {
        "key": card_key,
        "filename": filename,
        "thinking_attempt": None,
        "non_thinking_attempt": None,
        "final_status": None,
        "output_path": str(output_json.relative_to(REPO)),
        "elapsed_s": 0.0,
    }

    if output_json.exists():
        if not force and looks_like_valid_output(output_json):
            record["final_status"] = "skipped_existing"
            return record
        # Stale/broken OR --force: wipe before running claude. Must happen
        # BEFORE invocation because the ocr prompt checks for existing
        # output and refuses to overwrite.
        output_json.unlink()

    if not original_image.exists():
        record["final_status"] = "missing_image"
        return record

    ensure_symlink(original_image, image_symlink)

    t0 = time.time()
    # --- Attempt 1: thinking on ---
    try:
        r1 = run_claude_once(image_symlink, prompt_name,
                             thinking=True,
                             max_tokens=max_tokens,
                             max_thinking_tokens=max_thinking_tokens,
                             timeout_s=timeout_s,
                             model=model,
                             effort=effort,
                             ref_image=ref_image)
        record["thinking_attempt"] = {
            "returncode": r1.returncode,
            "stderr_tail": (r1.stderr or "")[-500:],
        }
    except subprocess.TimeoutExpired:
        record["thinking_attempt"] = {"returncode": None, "error": "timeout"}

    if looks_like_valid_output(output_json):
        record["final_status"] = "ok_thinking"
        record["elapsed_s"] = round(time.time() - t0, 2)
        return record

    # Attempt 1 produced nothing usable — wipe any partial file and retry
    if output_json.exists():
        output_json.unlink()

    # --- Attempt 2: thinking off ---
    try:
        r2 = run_claude_once(image_symlink, prompt_name,
                             thinking=False,
                             max_tokens=max_tokens,
                             max_thinking_tokens=0,
                             timeout_s=timeout_s,
                             model=model,
                             effort=effort,
                             ref_image=ref_image)
        record["non_thinking_attempt"] = {
            "returncode": r2.returncode,
            "stderr_tail": (r2.stderr or "")[-500:],
        }
    except subprocess.TimeoutExpired:
        record["non_thinking_attempt"] = {"returncode": None, "error": "timeout"}

    if looks_like_valid_output(output_json):
        record["final_status"] = "ok_fallback"
    else:
        record["final_status"] = "failed"

    record["elapsed_s"] = round(time.time() - t0, 2)
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True, help="Slash-command name (without leading /)")
    ap.add_argument("--run-id", required=True, help="Short id for this run (e.g. baseline, v1)")
    ap.add_argument("--sample", required=True, type=Path, help="Path to a sample_*.json")
    ap.add_argument("--source-folder", default="Auto-Color0002_oriented",
                    help="Subfolder under output/ where canonical images live")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--max-thinking-tokens", type=int, default=2048)
    ap.add_argument("--timeout", type=int, default=180, help="Seconds per card")
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="Overwrite existing run outputs")
    ap.add_argument("--model", default=None,
                    help="Claude model alias or full name (e.g. 'sonnet', 'opus', 'claude-opus-4-5')")
    ap.add_argument("--effort", default=None,
                    help="Effort level: low, medium, high, max")
    ap.add_argument("--reference-image", default=None, type=Path,
                    help="Path to a reference image prepended to each card invocation")
    args = ap.parse_args()

    args.sample = args.sample.resolve()
    sample = json.loads(args.sample.read_text())
    cards = sample.get("cards", [])
    if not cards:
        sys.exit(f"Empty sample: {args.sample}")

    # Safety: fall back to original folder if _oriented doesn't exist yet
    source_folder = args.source_folder
    if not (REPO / "output" / source_folder).is_dir():
        fallback = "Auto-Color0002"
        print(f"[warn] {source_folder} not found, falling back to {fallback}")
        source_folder = fallback

    run_dir = REPO / "output" / source_folder / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    RUNS_META_DIR.mkdir(exist_ok=True)
    manifest_path = RUNS_META_DIR / f"{args.run_id}.json"

    print(f"run {args.run_id!r}: prompt=/{args.prompt}  source={source_folder}  cards={len(cards)}")
    print(f"  thinking budget: {args.max_thinking_tokens}  max output: {args.max_tokens}  parallel: {args.parallel}")
    print(f"  run dir: output/{source_folder}/runs/{args.run_id}/")

    records = []
    t_start = time.time()

    def work(c):
        return process_card(
            c["key"],
            source_folder=source_folder,
            prompt_name=args.prompt,
            run_id=args.run_id,
            max_tokens=args.max_tokens,
            max_thinking_tokens=args.max_thinking_tokens,
            timeout_s=args.timeout,
            force=args.force,
            model=args.model,
            effort=args.effort,
            ref_image=args.reference_image,
        )

    try:
        if args.parallel <= 1:
            for i, c in enumerate(cards, 1):
                rec = work(c)
                records.append(rec)
                print(f"  [{i:>3}/{len(cards)}] {rec['final_status']:18} {rec['filename']:15} ({rec['elapsed_s']}s)")
        else:
            with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
                futures = {ex.submit(work, c): c for c in cards}
                done = 0
                for fut in cf.as_completed(futures):
                    rec = fut.result()
                    records.append(rec)
                    done += 1
                    print(f"  [{done:>3}/{len(cards)}] {rec['final_status']:18} {rec['filename']:15} ({rec['elapsed_s']}s)")
    except KeyboardInterrupt:
        print("\n[interrupted]")

    elapsed = round(time.time() - t_start, 1)
    counts = {}
    for r in records:
        counts[r["final_status"]] = counts.get(r["final_status"], 0) + 1

    manifest = {
        "run_id": args.run_id,
        "prompt": args.prompt,
        "source_folder": source_folder,
        "sample_path": str(args.sample.relative_to(REPO)),
        "n_cards": len(cards),
        "elapsed_s": elapsed,
        "max_tokens": args.max_tokens,
        "max_thinking_tokens": args.max_thinking_tokens,
        "model": args.model,
        "effort": args.effort,
        "reference_image": str(args.reference_image) if args.reference_image else None,
        "status_counts": counts,
        "records": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\ndone in {elapsed}s — {counts}")
    print(f"manifest: {manifest_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
