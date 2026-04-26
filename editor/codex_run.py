#!/usr/bin/env python3
"""Codex CLI parallel harness — mirror of editor/eval_run.py for OpenAI Codex.

Per card, we invoke `codex exec` in headless mode with the image attached
and the OCR prompt body inlined. Output shape is enforced via
--output-schema (editor/codex_schema.json) and written directly to disk
via -o, so we don't need a Write-tool detour.

The on-disk layout mirrors eval_run.py exactly so score_run.py works
unchanged:

    output/<source>/runs/<run-id>/<stem>.json   per-card outputs
    editor/runs/<run-id>.json                   manifest

Prerequisites:
  - codex CLI on PATH (install via the upstream installer at
    github.com/openai/codex/releases or `npm install -g @openai/codex`)
  - Authentication: either OPENAI_API_KEY exported, or `codex login` for
    subscription auth. Subscription auth is throttled by the 5-hour
    message window, which can stall a long batch — fine on OSS plan,
    not recommended for the full 152-card corpus on a Plus seat.

Usage:
    python editor/codex_run.py \\
        --prompt perestoroha_ocr_preset \\
        --run-id codex_test \\
        --sample editor/samples/test_split.json \\
        --model gpt-5.5 \\
        --max-parallel 1
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
PROMPTS_DIR = REPO / ".claude" / "commands"
SCHEMA_PATH = HERE / "codex_schema.json"

# STEP 4 of the Claude prompt instructs the model to call the Write tool.
# Codex uses --output-schema + -o for that, so we override the instruction
# at the end of the prompt rather than maintaining a forked copy.
CODEX_OVERRIDE = (
    "\n\n---\n\n"
    "OVERRIDE FOR THIS RUN: ignore the STEP 4 / SAVE OUTPUT instructions "
    "above. Do NOT call any tool to write a file. Output the JSON object "
    "directly as your final response — the runtime will persist it."
)


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        sys.exit(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8") + CODEX_OVERRIDE


def looks_like_valid_output(p: Path) -> bool:
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return isinstance(d, dict) and "filename" in d
    except Exception:
        return False


def run_codex_once(image: Path, output: Path, *, prompt_body: str,
                   model: str, timeout_s: int) -> subprocess.CompletedProcess:
    cmd = [
        "codex", "exec",
        "--skip-git-repo-check",
        "--full-auto",
        "--json",
        "-m", model,
        "-i", str(image),
        "--output-schema", str(SCHEMA_PATH),
        "-o", str(output),
        prompt_body,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        cwd=str(REPO),
    )


def process_card(card_key: str, *, source_folder: str, prompt_body: str,
                 run_id: str, model: str, timeout_s: int, force: bool) -> dict:
    folder, filename = card_key.split("/", 1)
    original_image = REPO / "output" / source_folder / filename
    run_dir = REPO / "output" / source_folder / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    output_json = run_dir / (Path(filename).stem + ".json")

    record = {
        "key": card_key,
        "filename": filename,
        "attempt": None,
        "final_status": None,
        "output_path": str(output_json.relative_to(REPO)),
        "elapsed_s": 0.0,
    }

    if output_json.exists():
        if not force and looks_like_valid_output(output_json):
            record["final_status"] = "skipped_existing"
            return record
        output_json.unlink()

    if not original_image.exists():
        record["final_status"] = "missing_image"
        return record

    t0 = time.time()
    try:
        r = run_codex_once(
            original_image, output_json,
            prompt_body=prompt_body, model=model, timeout_s=timeout_s,
        )
        record["attempt"] = {
            "returncode": r.returncode,
            "stderr_tail": (r.stderr or "")[-500:],
        }
    except subprocess.TimeoutExpired:
        record["attempt"] = {"returncode": None, "error": "timeout"}

    if looks_like_valid_output(output_json):
        record["final_status"] = "ok"
    else:
        record["final_status"] = "failed"

    record["elapsed_s"] = round(time.time() - t0, 2)
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True,
                    help="Prompt file stem under .claude/commands/ (e.g. perestoroha_ocr_preset)")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--sample", required=True, type=Path)
    ap.add_argument("--source-folder", default="Auto-Color0002_oriented")
    ap.add_argument("--model", default="gpt-5.5",
                    help="OpenAI model id (gpt-5.5, gpt-5.4, ...)")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--max-parallel", type=int, default=1,
                    help="Concurrent codex processes; default 1 (strictly sequential)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if shutil.which("codex") is None:
        sys.exit("codex CLI not found on PATH. Install via the upstream installer or `npm install -g @openai/codex`.")
    if not os.environ.get("OPENAI_API_KEY"):
        # Subscription auth (`codex login`) is also fine. We don't fail here —
        # if no auth is configured at all, codex itself will error out per call.
        print("[info] OPENAI_API_KEY not set; relying on `codex login` subscription auth.", file=sys.stderr)

    args.sample = args.sample.resolve()
    sample = json.loads(args.sample.read_text())
    cards = sample.get("cards", [])
    if not cards:
        sys.exit(f"empty sample: {args.sample}")

    source_folder = args.source_folder
    if not (REPO / "output" / source_folder).is_dir():
        sys.exit(f"source folder missing: output/{source_folder}")

    prompt_body = load_prompt(args.prompt)
    run_dir = REPO / "output" / source_folder / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    RUNS_META_DIR.mkdir(exist_ok=True)
    manifest_path = RUNS_META_DIR / f"{args.run_id}.json"

    print(f"run {args.run_id!r}: prompt={args.prompt}  model={args.model}  "
          f"source={source_folder}  cards={len(cards)}  parallel={args.max_parallel}")
    print(f"  run dir: output/{source_folder}/runs/{args.run_id}/")

    records = []
    t_start = time.time()

    def work(c):
        return process_card(
            c["key"],
            source_folder=source_folder,
            prompt_body=prompt_body,
            run_id=args.run_id,
            model=args.model,
            timeout_s=args.timeout,
            force=args.force,
        )

    try:
        if args.max_parallel <= 1:
            for i, c in enumerate(cards, 1):
                rec = work(c)
                records.append(rec)
                print(f"  [{i:>3}/{len(cards)}] {rec['final_status']:18} "
                      f"{rec['filename']:15} ({rec['elapsed_s']}s)")
        else:
            with cf.ThreadPoolExecutor(max_workers=args.max_parallel) as ex:
                futures = {ex.submit(work, c): c for c in cards}
                done = 0
                for fut in cf.as_completed(futures):
                    rec = fut.result()
                    records.append(rec)
                    done += 1
                    print(f"  [{done:>3}/{len(cards)}] {rec['final_status']:18} "
                          f"{rec['filename']:15} ({rec['elapsed_s']}s)")
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
        "sample_path": str(args.sample.relative_to(REPO)) if args.sample.is_relative_to(REPO) else str(args.sample),
        "n_cards": len(cards),
        "elapsed_s": elapsed,
        "model": args.model,
        "cli": "codex",
        "max_parallel": args.max_parallel,
        "status_counts": counts,
        "records": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\ndone in {elapsed}s — {counts}")
    print(f"manifest: {manifest_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
