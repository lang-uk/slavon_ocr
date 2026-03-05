#!/usr/bin/env python3
"""Flask proofreading editor for OCR'd historical cards."""

from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from db import get_db, init_db

app = Flask(__name__)
OUTPUT_DIR = Path(__file__).parent.parent / "output"


@app.before_request
def before_request():
    init_db()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    conn = get_db()
    folders = conn.execute("""
        SELECT folder,
               COUNT(*) as total,
               SUM(reviewed) as reviewed,
               SUM(deleted) as deleted_count,
               SUM(CASE WHEN lines IS NULL OR lines = '' THEN 1 ELSE 0 END) as blank
        FROM cards
        GROUP BY folder
        ORDER BY folder
    """).fetchall()
    conn.close()
    return render_template("index.html", folders=folders)


@app.route("/edit/<folder>")
def edit_redirect(folder):
    """Redirect to first card in folder (respecting filters)."""
    conn = get_db()
    filt = request.args.get("filter", "all")
    card = _filtered_query(conn, folder, filt, limit=1)
    conn.close()
    if not card:
        return redirect(url_for("index"))
    return redirect(url_for("edit_card", folder=folder, card_id=card[0]["id"], filter=filt))


@app.route("/edit/<folder>/<int:card_id>")
def edit_card(folder, card_id):
    conn = get_db()
    card = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    if not card or card["folder"] != folder:
        abort(404)

    filt = request.args.get("filter", "all")
    all_ids = [r["id"] for r in _filtered_query(conn, folder, filt)]

    if card_id not in all_ids:
        # Card exists but doesn't match filter — show it anyway, but nav uses 'all'
        all_ids = [r["id"] for r in _filtered_query(conn, folder, "all")]
        filt = "all"

    current_idx = all_ids.index(card_id) if card_id in all_ids else 0
    prev_id = all_ids[current_idx - 1] if current_idx > 0 else None
    next_id = all_ids[current_idx + 1] if current_idx < len(all_ids) - 1 else None

    # Card counts for status bar
    counts = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(reviewed) as reviewed,
               SUM(deleted) as deleted_count
        FROM cards WHERE folder = ?
    """, (folder,)).fetchone()

    conn.close()

    return render_template(
        "editor.html",
        card=card,
        folder=folder,
        prev_id=prev_id,
        next_id=next_id,
        current_idx=current_idx,
        total_filtered=len(all_ids),
        counts=counts,
        current_filter=filt,
    )


@app.route("/save/<int:card_id>", methods=["POST"])
def save_card(card_id):
    conn = get_db()
    card = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    if not card:
        abort(404)

    folder = card["folder"]
    filt = request.form.get("current_filter", "all")

    lines = request.form.get("lines", "")
    reviewed = 1 if request.form.get("reviewed") else 0
    deleted = 1 if request.form.get("deleted") else 0

    reviewed_at = card["reviewed_at"]
    if reviewed and not card["reviewed"]:
        reviewed_at = datetime.now(timezone.utc).isoformat()
    elif not reviewed:
        reviewed_at = None

    conn.execute(
        """UPDATE cards SET
            card_num_primary = ?,
            card_num_secondary = ?,
            card_num_tertiary = ?,
            card_num_notes = ?,
            lines = ?,
            source_city = ?,
            source_date = ?,
            source_reference = ?,
            notes = ?,
            deleted = ?,
            reviewed = ?,
            reviewed_at = ?
        WHERE id = ?""",
        (
            request.form.get("card_num_primary") or None,
            request.form.get("card_num_secondary") or None,
            request.form.get("card_num_tertiary") or None,
            request.form.get("card_num_notes") or None,
            lines,
            request.form.get("source_city") or None,
            request.form.get("source_date") or None,
            request.form.get("source_reference") or None,
            request.form.get("notes") or None,
            deleted,
            reviewed,
            reviewed_at,
            card_id,
        ),
    )
    conn.commit()

    # Navigate to next card if requested
    direction = request.form.get("direction", "stay")
    if direction in ("next", "prev"):
        all_ids = [r["id"] for r in _filtered_query(conn, folder, filt)]
        if card_id in all_ids:
            idx = all_ids.index(card_id)
            if direction == "next" and idx < len(all_ids) - 1:
                conn.close()
                return redirect(url_for("edit_card", folder=folder, card_id=all_ids[idx + 1], filter=filt))
            elif direction == "prev" and idx > 0:
                conn.close()
                return redirect(url_for("edit_card", folder=folder, card_id=all_ids[idx - 1], filter=filt))

    conn.close()
    return redirect(url_for("edit_card", folder=folder, card_id=card_id, filter=filt))


@app.route("/image/<folder>/<filename>")
def serve_image(folder, filename):
    image_path = OUTPUT_DIR / folder / filename
    if not image_path.is_file():
        abort(404)
    return send_file(image_path)


@app.route("/jump/<folder>", methods=["POST"])
def jump_to_card(folder):
    filt = request.form.get("current_filter", "all")
    target = request.form.get("jump_target", "").strip()

    conn = get_db()

    # Try to match by filename first
    card = conn.execute(
        "SELECT id FROM cards WHERE folder = ? AND filename LIKE ?",
        (folder, f"%{target}%"),
    ).fetchone()

    # Try by card number
    if not card:
        card = conn.execute(
            "SELECT id FROM cards WHERE folder = ? AND card_num_primary = ?",
            (folder, target),
        ).fetchone()

    # Try by index in filtered list
    if not card:
        try:
            idx = int(target) - 1
            all_ids = [r["id"] for r in _filtered_query(conn, folder, filt)]
            if 0 <= idx < len(all_ids):
                conn.close()
                return redirect(url_for("edit_card", folder=folder, card_id=all_ids[idx], filter=filt))
        except ValueError:
            pass

    conn.close()
    if card:
        return redirect(url_for("edit_card", folder=folder, card_id=card["id"], filter=filt))
    return redirect(url_for("edit_redirect", folder=folder, filter=filt))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _filtered_query(conn, folder, filt, limit=None):
    where = "folder = ?"
    params = [folder]

    if filt == "unreviewed":
        where += " AND reviewed = 0 AND deleted = 0"
    elif filt == "reviewed":
        where += " AND reviewed = 1"
    elif filt == "deleted":
        where += " AND deleted = 1"
    elif filt == "has_notes":
        where += " AND notes IS NOT NULL AND notes != ''"
    elif filt == "errors":
        where += " AND error_type IS NOT NULL"

    sql = f"SELECT id FROM cards WHERE {where} ORDER BY filename"
    if limit:
        sql += f" LIMIT {limit}"
    return conn.execute(sql, params).fetchall()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
