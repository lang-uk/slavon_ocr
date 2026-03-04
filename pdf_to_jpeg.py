#!/usr/bin/env python3
"""Convert a scanned PDF into individual JPEG files, preserving original image quality."""

import argparse
import math
import sys
from pathlib import Path

import fitz  # PyMuPDF


def extract_images(pdf_path: Path, output_dir: Path) -> None:
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    zero_pad = max(len(str(num_pages)), 1)

    output_dir.mkdir(parents=True, exist_ok=True)

    for page_num in range(num_pages):
        page = doc[page_num]
        images = page.get_images(full=True)

        if len(images) == 1:
            # Single image per page — extract the raw image bytes directly
            xref = images[0][0]
            base_image = doc.extract_image(xref)
            ext = base_image["ext"]
            image_bytes = base_image["image"]

            out_file = output_dir / f"{page_num + 1:0{zero_pad}d}.jpeg"

            if ext in ("jpeg", "jpg"):
                # Already JPEG — write as-is for lossless preservation
                out_file.write_bytes(image_bytes)
            else:
                # Non-JPEG source (png, etc.) — convert via Pillow
                from PIL import Image
                import io

                img = Image.open(io.BytesIO(image_bytes))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(out_file, "JPEG", quality=98)
        else:
            # Multiple or no embedded images — render the full page at high DPI
            pix = page.get_pixmap(dpi=300)
            out_file = output_dir / f"{page_num + 1:0{zero_pad}d}.jpeg"

            from PIL import Image

            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            img.save(out_file, "JPEG", quality=98)

        print(f"  [{page_num + 1}/{num_pages}] {out_file.name}")

    doc.close()
    print(f"Done — {num_pages} page(s) saved to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a scanned PDF into individual JPEG files."
    )
    parser.add_argument("pdf", type=Path, help="Path to the input PDF file")
    parser.add_argument("output_dir", type=Path, help="Path to the output folder")
    args = parser.parse_args()

    if not args.pdf.is_file():
        sys.exit(f"Error: {args.pdf} is not a file")

    print(f"Processing {args.pdf} ...")
    extract_images(args.pdf, args.output_dir)


if __name__ == "__main__":
    main()
