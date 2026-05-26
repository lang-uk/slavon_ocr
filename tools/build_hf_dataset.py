"""Build the Hugging Face dataset release from editor/cards.db.

Reads:
  - editor/cards.db (reviewed=1, deleted=0 → 430 cards)
  - editor/samples/test_split.json (30 cards) → HF "test" split
  - editor/samples/dev_split.json (122 cards) → HF "validation" split
  - the remaining 278 cards → HF "train" split
  - output/Auto-Color0002_oriented/<filename> for image bytes

Writes:
  - dataset/data/train-00000-of-00001.parquet
  - dataset/data/validation-00000-of-00001.parquet
  - dataset/data/test-00000-of-00001.parquet

Schema (per record):
  id                  Auto-Color0002/001
  image               PIL image (300 DPI JPEG, EXIF-rotated to upright)
  transcription       proofread text, line breaks preserved
  card_num_primary    string | null
  card_num_secondary  string | null
  card_num_tertiary   string | null
  card_num_notes      string | null
  source_city         string | null
  source_date         string | null
  source_reference    string | null
  notes               string | null
  reviewed_at         ISO timestamp string

Run:
  ./.venv/bin/python tools/build_hf_dataset.py
"""

import json
import sqlite3
from pathlib import Path

from datasets import Dataset, Features, Image, Value

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "editor" / "cards.db"
IMG_DIR = REPO / "output" / "Auto-Color0002_oriented"
SAMPLES_DIR = REPO / "editor" / "samples"
OUT_DIR = REPO / "dataset" / "data"

FEATURES = Features({
    "id": Value("string"),
    "image": Image(),
    "transcription": Value("string"),
    "card_num_primary": Value("string"),
    "card_num_secondary": Value("string"),
    "card_num_tertiary": Value("string"),
    "card_num_notes": Value("string"),
    "source_city": Value("string"),
    "source_date": Value("string"),
    "source_reference": Value("string"),
    "notes": Value("string"),
    "reviewed_at": Value("string"),
})


def load_split_keys(path: Path) -> set[str]:
    data = json.loads(path.read_text())
    return {c["key"] for c in data["cards"]}


def make_record(row, img_path: Path) -> dict:
    return {
        "id": f"{row['folder']}/{Path(row['filename']).stem}",
        "image": {"bytes": img_path.read_bytes(), "path": img_path.name},
        "transcription": row["lines"],
        "card_num_primary": row["card_num_primary"],
        "card_num_secondary": row["card_num_secondary"],
        "card_num_tertiary": row["card_num_tertiary"],
        "card_num_notes": row["card_num_notes"],
        "source_city": row["source_city"],
        "source_date": row["source_date"],
        "source_reference": row["source_reference"],
        "notes": row["notes"],
        "reviewed_at": row["reviewed_at"],
    }


def main():
    test_keys = load_split_keys(SAMPLES_DIR / "test_split.json")
    dev_keys = load_split_keys(SAMPLES_DIR / "dev_split.json")
    assert len(test_keys) == 30, len(test_keys)
    assert len(dev_keys) == 122, len(dev_keys)
    assert not (test_keys & dev_keys), "test/dev splits overlap"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM cards WHERE reviewed=1 AND deleted=0 ORDER BY folder, filename"
    ).fetchall()
    print(f"loaded {len(rows)} proofread cards from {DB_PATH}")

    splits = {"train": [], "validation": [], "test": []}
    missing_images = []
    for row in rows:
        key = f"{row['folder']}/{row['filename']}"
        img_path = IMG_DIR / row["filename"]
        if not img_path.exists():
            missing_images.append(key)
            continue
        rec = make_record(row, img_path)
        if key in test_keys:
            splits["test"].append(rec)
        elif key in dev_keys:
            splits["validation"].append(rec)
        else:
            splits["train"].append(rec)

    if missing_images:
        raise SystemExit(f"missing images for {len(missing_images)} cards: {missing_images[:5]}")

    for split, records in splits.items():
        print(f"  {split}: {len(records)} cards")
    assert sum(len(v) for v in splits.values()) == len(rows)
    assert len(splits["test"]) == 30
    assert len(splits["validation"]) == 122

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for split, records in splits.items():
        ds = Dataset.from_list(records, features=FEATURES)
        out = OUT_DIR / f"{split}-00000-of-00001.parquet"
        ds.to_parquet(str(out))
        print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
