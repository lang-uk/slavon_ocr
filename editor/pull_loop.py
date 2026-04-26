#!/usr/bin/env python3
"""Helper for the in-CC OCR pull loop.

Two subcommands used by the /ocr_pull_one skill:

    pull_loop.py next
        Print the absolute path of the next pending card image (one that
        exists in the oriented folder but is NOT yet in cards.db). Print
        an empty string when the pool is exhausted.

    pull_loop.py ingest <image_path> <ocr_json_path>
        Insert a draft cards row from a Claude-produced OCR JSON. The row
        is marked reviewed=0 so it surfaces in the proofreading editor.

The loop's durable state is the cards table itself: a card is "pending"
iff its filename is missing from cards. No queue file, no flags, no
mid-flight state — survives autocompaction and session restarts.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = Path(__file__).parent / "cards.db"
ORIENTED_DIR = REPO / "output" / "Auto-Color0002_oriented"
FOLDER = "Auto-Color0002"


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def cmd_next(_args):
    conn = _connect()
    have = {row[0] for row in conn.execute("SELECT filename FROM cards").fetchall()}
    conn.close()
    on_disk = sorted(p.name for p in ORIENTED_DIR.iterdir() if p.suffix.lower() in {".jpeg", ".jpg", ".png"})
    pending = [n for n in on_disk if n not in have]
    if not pending:
        print("")
        return 0
    print(str(ORIENTED_DIR / pending[0]))
    return 0


def cmd_ingest(args):
    image = Path(args.image_path).resolve()
    json_path = Path(args.json_path).resolve()
    if not json_path.exists():
        print(f"ERROR: ocr json not found: {json_path}", file=sys.stderr)
        return 2

    raw = json_path.read_text(encoding="utf-8")
    data = json.loads(raw)

    filename = image.name
    image_path_rel = str(image.relative_to(REPO)) if image.is_relative_to(REPO) else str(image)

    cn = data.get("card_numbers") or {}
    src = data.get("source") or {}
    lines = data.get("lines")
    lines_text = "\r\n".join(lines) if isinstance(lines, list) else None

    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO cards (
                folder, filename, image_path,
                card_num_primary, card_num_secondary, card_num_tertiary, card_num_notes,
                lines, source_city, source_date, source_reference,
                notes, deleted, reviewed, error_type, original_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)""",
            (
                FOLDER, filename, image_path_rel,
                cn.get("primary"), cn.get("secondary"), cn.get("tertiary"), cn.get("notes"),
                lines_text,
                src.get("city") if isinstance(src, dict) else None,
                src.get("date") if isinstance(src, dict) else None,
                src.get("reference") if isinstance(src, dict) else None,
                data.get("notes") or "",
                data.get("error_type"),
                raw,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        print(f"ERROR: insert failed (likely duplicate {FOLDER}/{filename}): {e}", file=sys.stderr)
        conn.close()
        return 3
    conn.close()
    print(f"ingested {filename}")
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("next")
    ing = sub.add_parser("ingest")
    ing.add_argument("image_path")
    ing.add_argument("json_path")
    args = p.parse_args()
    if args.cmd == "next":
        sys.exit(cmd_next(args))
    elif args.cmd == "ingest":
        sys.exit(cmd_ingest(args))


if __name__ == "__main__":
    main()
