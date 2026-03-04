#!/usr/bin/env python3
"""Batch OCR: run the /ocr Claude Code skill on every image in a folder."""

import argparse
import subprocess
import sys
from pathlib import Path

IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".tiff", ".tif", ".bmp"}


def get_images(folder: Path) -> list[Path]:
    """Return sorted list of image files in the folder."""
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def has_transcription(image_path: Path) -> bool:
    """Check if a .json transcription already exists for this image."""
    return image_path.with_suffix(".json").exists()


def run_ocr(image_path: Path) -> bool:
    """Invoke Claude Code /ocr skill on a single image. Returns True on success."""
    result = subprocess.run(
        [
            "claude",
            "--allowedTools", "Write",
            "-p", f"/ocr @{image_path}",
        ],
        capture_output=False,
    )
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-run /ocr on every image in a folder via Claude Code."
    )
    parser.add_argument("folder", type=Path, help="Folder containing images to OCR")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-transcribe even if .json already exists",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of images to process (0 = unlimited)",
    )
    args = parser.parse_args()

    folder = args.folder.resolve()
    if not folder.is_dir():
        sys.exit(f"Error: {folder} is not a directory")

    images = get_images(folder)
    if not images:
        sys.exit(f"No image files found in {folder}")

    total = len(images)
    skipped = 0
    done = 0
    failed = 0

    print(f"Found {total} image(s) in {folder}")

    try:
        for i, img in enumerate(images, 1):
            if has_transcription(img) and not args.force:
                skipped += 1
                print(f"[{i}/{total}] SKIP {img.name} (transcription exists)")
                continue

            if args.limit and done + failed >= args.limit:
                print(f"[{i}/{total}] STOP limit of {args.limit} reached")
                break

            print(f"[{i}/{total}] OCR  {img.name} ...")
            ok = run_ocr(img)
            if ok and has_transcription(img):
                done += 1
                print(f"[{i}/{total}] OK   {img.name}")
            else:
                failed += 1
                print(f"[{i}/{total}] FAIL {img.name}")
    except KeyboardInterrupt:
        print(f"\n\nInterrupted at image {i}/{total}.")

    print(
        f"\nDone: {done} transcribed, {skipped} skipped, {failed} failed (of {total})"
    )


if __name__ == "__main__":
    main()
