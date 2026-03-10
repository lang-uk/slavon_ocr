#!/usr/bin/env python3
"""One-off migration: ensure every card has the source metadata line in its transcription.

For cards where the OCR didn't include the source line (earlier prompt version),
reconstruct it from the structured source fields and append to both the proofread
text and the original_json. Uncheck reviewed so the reviewer can verify.

Safe to run multiple times — skips cards that already have the source line.
"""

import json
import sys
from db import get_db, init_db


def build_source_line(row):
    """Reconstruct the source line from DB columns: 'Львів, 1605-1606, Перест. 28.'"""
    parts = []
    if row["source_city"]:
        parts.append(row["source_city"])
    if row["source_date"]:
        parts.append(row["source_date"])
    if row["source_reference"]:
        parts.append(row["source_reference"])
    return ", ".join(parts) if parts else None


def has_source_line(text, ref):
    """Check if the source reference is already in the last line."""
    if not text or not ref:
        return False
    ref_clean = ref.strip().rstrip(".")
    last_line = text.strip().split("\n")[-1].strip()
    return ref_clean.lower() in last_line.lower()


def main():
    init_db()
    conn = get_db()

    rows = conn.execute("""
        SELECT id, filename, folder, lines, original_json,
               source_city, source_date, source_reference,
               reviewed, error_type
        FROM cards
        WHERE error_type IS NULL
        ORDER BY folder, filename
    """).fetchall()

    updated = 0
    skipped_has_line = 0
    skipped_no_source = 0

    for row in rows:
        source_line = build_source_line(row)
        if not source_line:
            skipped_no_source += 1
            continue

        ref = (row["source_reference"] or "").strip()

        # Check original_json lines
        ocr_data = json.loads(row["original_json"])
        ocr_lines = ocr_data.get("lines") or []
        ocr_text = "\n".join(ocr_lines)

        # Check proofread lines
        proof_text = (row["lines"] or "").replace("\r", "").strip()

        ocr_has = has_source_line(ocr_text, ref)
        proof_has = has_source_line(proof_text, ref)

        if ocr_has and proof_has:
            skipped_has_line += 1
            continue

        # Need to update — append source line where missing
        new_ocr_data = ocr_data.copy()
        new_proof_text = proof_text

        if not ocr_has and ocr_lines:
            new_ocr_data["lines"] = ocr_lines + [source_line]

        if not proof_has and proof_text:
            new_proof_text = proof_text + "\n" + source_line

        new_original_json = json.dumps(new_ocr_data, ensure_ascii=False, indent=2)

        conn.execute("""
            UPDATE cards SET
                lines = ?,
                original_json = ?,
                reviewed = 0,
                reviewed_at = NULL
            WHERE id = ?
        """, (new_proof_text, new_original_json, row["id"]))

        status = []
        if not ocr_has:
            status.append("ocr")
        if not proof_has:
            status.append("proof")
        print(f"  {row['filename']}: added source line to {'+'.join(status)}, unreviewed")
        updated += 1

    conn.commit()
    conn.close()

    print(f"\nDone: {updated} updated, {skipped_has_line} already had source line, "
          f"{skipped_no_source} no source metadata")


if __name__ == "__main__":
    main()
