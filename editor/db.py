"""Database setup and helpers for the card proofreading editor."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cards.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cards (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            folder          TEXT NOT NULL,
            filename        TEXT NOT NULL,
            image_path      TEXT NOT NULL,

            card_num_primary    TEXT,
            card_num_secondary  TEXT,
            card_num_tertiary   TEXT,
            card_num_notes      TEXT,

            lines           TEXT,
            source_city     TEXT,
            source_date     TEXT,
            source_reference TEXT,
            notes           TEXT,

            deleted         INTEGER DEFAULT 0,
            reviewed        INTEGER DEFAULT 0,
            reviewed_at     TEXT,
            error_type      TEXT,

            original_json   TEXT NOT NULL,

            UNIQUE(folder, filename)
        );

        CREATE INDEX IF NOT EXISTS idx_cards_folder ON cards(folder);
        CREATE INDEX IF NOT EXISTS idx_cards_reviewed ON cards(folder, reviewed);
        CREATE INDEX IF NOT EXISTS idx_cards_deleted ON cards(folder, deleted);
    """)
    conn.commit()
    conn.close()
