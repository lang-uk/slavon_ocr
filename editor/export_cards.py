#!/usr/bin/env python3
"""Export proofread cards from the editor database back to JSON files."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from db import get_db

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def export_folder(folder_name: str, suffix: str = "_proofread"):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM cards WHERE folder = ? ORDER BY filename", (folder_name,)
    ).fetchall()

    if not rows:
        print(f"  No cards found for {folder_name}")
        return

    exported = 0
    for row in rows:
        lines_list = row["lines"].split("\n") if row["lines"] else None

        data = {
            "filename": row["filename"],
            "card_numbers": {
                "primary": row["card_num_primary"],
                "secondary": row["card_num_secondary"],
                "tertiary": row["card_num_tertiary"],
                "notes": row["card_num_notes"],
            },
            "lines": lines_list,
            "source": {
                "city": row["source_city"],
                "date": row["source_date"],
                "reference": row["source_reference"],
            }
            if any([row["source_city"], row["source_date"], row["source_reference"]])
            else None,
            "notes": row["notes"] or "",
            "deleted": bool(row["deleted"]),
            "reviewed": bool(row["reviewed"]),
            "reviewed_at": row["reviewed_at"],
        }

        if row["error_type"]:
            data["error_type"] = row["error_type"]

        stem = Path(row["filename"]).stem
        out_path = OUTPUT_DIR / folder_name / f"{stem}{suffix}.json"
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        exported += 1

    conn.close()
    print(f"  {folder_name}: {exported} cards exported to *{suffix}.json")


def main():
    parser = argparse.ArgumentParser(description="Export proofread cards to JSON")
    parser.add_argument(
        "folders",
        nargs="*",
        help="Folder names to export (default: all)",
    )
    parser.add_argument(
        "--suffix",
        default="_proofread",
        help="Suffix for output JSON files (default: _proofread)",
    )
    args = parser.parse_args()

    conn = get_db()
    if args.folders:
        folder_names = args.folders
    else:
        folder_names = [
            r["folder"]
            for r in conn.execute("SELECT DISTINCT folder FROM cards ORDER BY folder")
        ]
    conn.close()

    for folder_name in folder_names:
        print(f"Exporting {folder_name}...")
        export_folder(folder_name, suffix=args.suffix)


if __name__ == "__main__":
    main()
