#!/usr/bin/env python3
"""Auto-orient JPEGs into a sibling `<folder>_oriented` directory.

Reads each JPEG's EXIF orientation tag, physically rotates the pixels into
normal reading orientation, strips the orientation tag, and writes the
result to a parallel directory. The canonical card set used by eval_run.py
points at this directory, so every run sees already-oriented images and
the VLM does not need to cope with upside-down input.

Why physical rotation (not just tag rewrite): it's not known whether
Claude's vision pipeline honors EXIF orientation, and relying on it is
fragile. Rotating pixels is a one-time cost and guarantees correctness
regardless of downstream consumers.

Usage:
    python editor/preprocess_orient.py Auto-Color0002
    python editor/preprocess_orient.py Auto-Color0002 --dry-run
    python editor/preprocess_orient.py Auto-Color0002 --force

Requires Pillow (pip install Pillow). The script errors out early if
Pillow is missing.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ExifTags
except ImportError:
    print("Pillow not installed. Run `pip install Pillow` first.", file=sys.stderr)
    sys.exit(2)

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "output"

# EXIF orientation → (PIL transpose method)
# 1 = normal, 2 = flip horizontal, 3 = 180, 4 = flip vertical,
# 5 = transpose, 6 = 90 CW, 7 = transverse, 8 = 90 CCW
ORIENTATION_OPS = {
    1: [],
    2: [Image.FLIP_LEFT_RIGHT],
    3: [Image.ROTATE_180],
    4: [Image.FLIP_TOP_BOTTOM],
    5: [Image.FLIP_LEFT_RIGHT, Image.ROTATE_90],
    6: [Image.ROTATE_270],   # 90° CW = PIL ROTATE_270
    7: [Image.FLIP_LEFT_RIGHT, Image.ROTATE_270],
    8: [Image.ROTATE_90],    # 90° CCW = PIL ROTATE_90
}

ORIENTATION_TAG = next(k for k, v in ExifTags.TAGS.items() if v == "Orientation")


def get_orientation(img: Image.Image):
    """Return EXIF orientation tag value, or None."""
    try:
        exif = img.getexif()
        return exif.get(ORIENTATION_TAG)
    except Exception:
        return None


def apply_ops(img: Image.Image, ops) -> Image.Image:
    for op in ops:
        img = img.transpose(op)
    return img


def process_folder(folder_name: str, dry_run: bool, force: bool) -> dict:
    src_dir = OUTPUT / folder_name
    dst_dir = OUTPUT / f"{folder_name}_oriented"
    if not src_dir.is_dir():
        sys.exit(f"Not a directory: {src_dir}")
    dst_dir.mkdir(parents=True, exist_ok=True)

    stats = {"total": 0, "rotated": 0, "portrait_fallback": 0,
             "copied_as_is": 0, "skipped_existing": 0, "rotations_by_exif": {}}
    log = []

    image_paths = sorted(
        p for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff")
    )

    for p in image_paths:
        stats["total"] += 1
        dst = dst_dir / p.name
        if dst.exists() and not force:
            stats["skipped_existing"] += 1
            continue

        try:
            img = Image.open(p)
            img.load()
        except Exception as e:
            log.append({"file": p.name, "error": f"open: {e}"})
            continue

        orient = get_orientation(img)
        ops = ORIENTATION_OPS.get(orient or 1, [])

        # Heuristic: if EXIF says nothing and the image is stored portrait
        # while we know these cards are landscape, rotate 90 CW as a guess.
        # Log it as a fallback so we can review.
        w, h = img.size
        was_portrait_fallback = False
        if not ops and h > w:
            ops = [Image.ROTATE_270]  # 90 CW
            was_portrait_fallback = True
            stats["portrait_fallback"] += 1

        if ops:
            stats["rotated"] += 1
            stats["rotations_by_exif"].setdefault(str(orient), 0)
            stats["rotations_by_exif"][str(orient)] += 1
        else:
            stats["copied_as_is"] += 1

        # When no rotation is needed, copy the original bytes untouched.
        # Re-encoding lossless formats through Pillow is fine; re-encoding
        # JPEGs at quality=92 causes a perceptible quality drift that
        # confuses the VLM on non-rotated cards (empirically verified).
        if not dry_run:
            if not ops:
                shutil.copy2(p, dst)
            else:
                out = apply_ops(img, ops)
                save_kwargs = {"quality": 95, "optimize": True, "subsampling": 0}
                if p.suffix.lower() in (".jpg", ".jpeg"):
                    out.convert("RGB").save(dst, "JPEG", **save_kwargs)
                else:
                    out.save(dst)

        log.append({
            "file": p.name,
            "orig_size": [w, h],
            "exif_orient": orient,
            "ops": [str(o) for o in ops],
            "portrait_fallback": was_portrait_fallback,
        })

    # Write change log
    if not dry_run:
        log_path = dst_dir / "_orient_log.json"
        log_path.write_text(json.dumps({"stats": stats, "log": log}, ensure_ascii=False, indent=2))

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="Folder name under output/ (e.g. Auto-Color0002)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing files in the _oriented folder")
    args = ap.parse_args()

    stats = process_folder(args.folder, args.dry_run, args.force)

    print(f"preprocess_orient: {args.folder}")
    print(f"  total:           {stats['total']}")
    print(f"  rotated:         {stats['rotated']}")
    print(f"  portrait fallback: {stats['portrait_fallback']}")
    print(f"  skipped existing: {stats['skipped_existing']}")
    print(f"  rotations by exif tag:")
    for k, v in sorted(stats["rotations_by_exif"].items()):
        print(f"    exif={k:>4}: {v}")
    if not args.dry_run:
        print(f"  wrote: output/{args.folder}_oriented/")
        print(f"  log:   output/{args.folder}_oriented/_orient_log.json")


if __name__ == "__main__":
    main()
