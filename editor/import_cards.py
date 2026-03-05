#!/usr/bin/env python3
"""Import OCR JSON files into the editor database."""

import argparse
import json
import sys
from pathlib import Path

from db import get_db, init_db

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def import_folder(folder_path: Path, force: bool = False):
    folder_name = folder_path.name
    conn = get_db()

    if force:
        deleted = conn.execute(
            "DELETE FROM cards WHERE folder = ?", (folder_name,)
        ).rowcount
        conn.commit()
        if deleted:
            print(f"  Cleared {deleted} existing records for {folder_name}")

    json_files = sorted(folder_path.glob("*.json"))
    imported = 0
    skipped = 0

    for jf in json_files:
        try:
            raw = jf.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  SKIP {jf.name}: {e}")
            skipped += 1
            continue

        filename = data.get("filename", jf.stem + ".jpeg")
        image_path = str(folder_path / filename)

        # Extract fields
        cn = data.get("card_numbers") or {}
        source = data.get("source") or {}
        lines_list = data.get("lines")
        lines_text = "\n".join(lines_list) if lines_list else None

        try:
            conn.execute(
                """INSERT INTO cards
                   (folder, filename, image_path,
                    card_num_primary, card_num_secondary, card_num_tertiary, card_num_notes,
                    lines, source_city, source_date, source_reference,
                    notes, error_type, original_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    folder_name,
                    filename,
                    image_path,
                    cn.get("primary"),
                    cn.get("secondary"),
                    cn.get("tertiary"),
                    cn.get("notes"),
                    lines_text,
                    source.get("city"),
                    source.get("date"),
                    source.get("reference"),
                    data.get("notes"),
                    data.get("error_type"),
                    raw,
                ),
            )
            imported += 1
        except Exception as e:
            if "UNIQUE constraint" in str(e):
                skipped += 1
            else:
                print(f"  ERROR {jf.name}: {e}")
                skipped += 1

    conn.commit()
    conn.close()
    print(f"  {folder_name}: {imported} imported, {skipped} skipped")


def main():
    parser = argparse.ArgumentParser(description="Import OCR JSONs into editor DB")
    parser.add_argument(
        "folders",
        nargs="*",
        help="Folder names under output/ to import (default: all)",
    )
    parser.add_argument("--force", action="store_true", help="Re-import (delete existing)")
    args = parser.parse_args()

    init_db()

    if args.folders:
        folders = [OUTPUT_DIR / f for f in args.folders]
    else:
        folders = sorted(
            p for p in OUTPUT_DIR.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )

    for folder in folders:
        if not folder.is_dir():
            print(f"  SKIP {folder}: not a directory")
            continue
        json_count = len(list(folder.glob("*.json")))
        if json_count == 0:
            print(f"  SKIP {folder.name}: no JSON files")
            continue
        print(f"Importing {folder.name} ({json_count} JSON files)...")
        import_folder(folder, force=args.force)

    # Print summary
    conn = get_db()
    for row in conn.execute(
        "SELECT folder, COUNT(*) as cnt, SUM(reviewed) as rev FROM cards GROUP BY folder"
    ):
        print(f"  DB total — {row['folder']}: {row['cnt']} cards ({row['rev'] or 0} reviewed)")
    conn.close()


if __name__ == "__main__":
    main()
