#!/usr/bin/env python3
"""Build an HTML demo page from OCR transcription JSONs and their source card images."""

import argparse
import html
import json
import sys
from pathlib import Path

from natsort import natsort_keygen

IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".tiff", ".tif", ".bmp"}

_nat_key = natsort_keygen()


def load_cards(folder: Path) -> list[dict]:
    """Load all .json transcription files from a folder, attaching image paths."""
    cards = []
    for jf in sorted(folder.glob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  WARN: skipping {jf.name}: {exc}", file=sys.stderr)
            continue

        # resolve matching image
        img_path = None
        stem = jf.stem
        for ext in IMAGE_EXTENSIONS:
            candidate = folder / (stem + ext)
            if candidate.exists():
                img_path = candidate
                break

        data["_json_path"] = str(jf)
        data["_image_path"] = str(img_path) if img_path else None
        data["_image_name"] = img_path.name if img_path else None
        cards.append(data)
    return cards


def sort_key(card: dict, field: str) -> tuple:
    """Natural sort key for the chosen field. Cards without the field sort last."""
    if field == "filename":
        val = card.get("filename")
    else:
        val = (card.get("card_numbers") or {}).get(field)

    if val is None:
        return (1, _nat_key(""))
    return (0, _nat_key(str(val)))


def esc(text: str | None) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def render_card(card: dict, idx: int, total: int, sort_field: str) -> str:
    """Render a single card as an HTML article."""
    cn = card.get("card_numbers") or {}
    source = card.get("source") or {}
    lines = card.get("lines")
    notes = card.get("notes") or ""
    error_type = card.get("error_type")
    filename = card.get("filename", "")

    # sort value — displayed as top-right badge
    if sort_field == "filename":
        sort_val = filename
    else:
        sort_val = cn.get(sort_field)
    sort_num_html = esc(str(sort_val)) if sort_val is not None else "—"

    # other card numbers (everything except the sort field)
    other_nums = []
    for key in ("primary", "secondary", "tertiary"):
        if key == sort_field:
            continue
        v = cn.get(key)
        if v is not None:
            other_nums.append(f'<span class="cn-label">{key[0].upper()}</span>{esc(str(v))}')
    other_cn_html = " &middot; ".join(other_nums) if other_nums else ""

    cn_notes = cn.get("notes", "")

    # source display
    src_parts = []
    if source.get("city"):
        src_parts.append(esc(source["city"]))
    if source.get("date"):
        src_parts.append(esc(source["date"]))
    if source.get("reference"):
        src_parts.append(f'<span class="ref">{esc(source["reference"])}</span>')
    src_html = ", ".join(src_parts) if src_parts else ""

    # lines / error
    if error_type:
        body_html = f'<div class="card-error">{esc(error_type)}: {esc(notes)}</div>'
    elif lines:
        rendered = "\n".join(f"<p>{esc(l)}</p>" for l in lines)
        body_html = f'<div class="card-lines">{rendered}</div>'
    else:
        body_html = '<div class="card-error">No transcription</div>'

    # image
    img_name = card.get("_image_name")
    if img_name:
        img_html = f'<img src="{esc(img_name)}" alt="Card {esc(filename)}" loading="lazy">'
    else:
        img_html = '<div class="no-image">No image</div>'

    # notes
    notes_html = ""
    if notes and not error_type:
        notes_html = f'<div class="card-notes"><span class="notes-label">Notes:</span> {esc(notes)}</div>'

    cn_notes_html = ""
    if cn_notes:
        cn_notes_html = f'<div class="cn-notes">{esc(cn_notes)}</div>'

    return f"""<article class="card" id="card-{idx}">
  <div class="card-col card-col-text">
    <div class="card-top-row">
      {f'<div class="card-numbers-other">{other_cn_html}</div>' if other_cn_html else ""}
      <div class="sort-number">{sort_num_html}</div>
    </div>
    {body_html}
    {notes_html}
    {f'<div class="card-source">{src_html}</div>' if src_html else ""}
    {cn_notes_html}
  </div>
  <div class="card-col card-col-image">
    <div class="card-image">{img_html}</div>
  </div>
</article>"""


def build_html(cards: list[dict], folder: Path, sort_field: str) -> str:
    total = len(cards)
    cards_html = "\n".join(render_card(c, i + 1, total, sort_field) for i, c in enumerate(cards))

    # jump-nav labels
    def nav_label(c: dict) -> str:
        if sort_field == "filename":
            return c.get("filename", "?")
        return str((c.get("card_numbers") or {}).get(sort_field) or c.get("filename", "?"))

    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Card Transcriptions</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,600;1,8..60,400&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #1a365d;
            --accent: #c53030;
            --accent-light: #feb2b2;
            --bg: #faf9f7;
            --card-bg: #ffffff;
            --text: #2d3748;
            --text-light: #718096;
            --text-muted: #a0aec0;
            --border: #e2e8f0;
            --shadow: 0 4px 6px -1px rgba(0,0,0,.1), 0 2px 4px -1px rgba(0,0,0,.06);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,.1), 0 4px 6px -2px rgba(0,0,0,.05);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Source Serif 4', Georgia, serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            padding: 2rem 1rem;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 3px double var(--border);
        }}

        header h1 {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 2.75rem;
            font-weight: 700;
            color: var(--primary);
            letter-spacing: -0.02em;
            margin-bottom: 0.5rem;
        }}

        header .subtitle {{
            font-family: 'Inter', sans-serif;
            font-size: 0.95rem;
            color: var(--text-light);
            font-weight: 300;
            text-transform: uppercase;
            letter-spacing: 0.15em;
        }}

        .stats {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1.5rem;
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
        }}

        .stat {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .stat-number {{
            font-weight: 600;
            color: var(--accent);
            font-size: 1.1rem;
        }}

        /* --- Card layout: two 50% columns --- */

        .card {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            background: var(--card-bg);
            border-radius: 12px;
            margin-bottom: 2rem;
            box-shadow: var(--shadow);
            overflow: hidden;
            border-left: 4px solid transparent;
            transition: box-shadow .3s ease, transform .2s ease, border-color .2s ease;
        }}

        .card:hover {{
            box-shadow: var(--shadow-lg);
            transform: translateY(-2px);
            border-left-color: var(--accent);
        }}

        .card-col-text {{
            padding: 1.5rem 2rem 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .card-col-image {{
            background: #f1f0ee;
            display: flex;
            align-items: flex-start;
            justify-content: center;
        }}

        /* --- Top row: other numbers left, sort badge right --- */

        .card-top-row {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.75rem;
        }}

        .sort-number {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--card-bg);
            background: var(--primary);
            min-width: 2.75rem;
            height: 2.75rem;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            flex-shrink: 0;
            padding: 0 0.65rem;
            line-height: 1;
            letter-spacing: -0.02em;
        }}

        .card-numbers-other {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-light);
            padding-top: 0.4rem;
        }}

        .cn-label {{
            font-family: 'Inter', sans-serif;
            font-size: 0.5rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            vertical-align: super;
            margin-right: 1px;
        }}

        .cn-notes {{
            font-family: 'Inter', sans-serif;
            font-size: 0.65rem;
            color: var(--text-muted);
            opacity: 0.6;
            font-style: italic;
            margin-top: auto;
        }}

        .card-source {{
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            color: var(--text-light);
            margin-top: 0.25rem;
        }}

        .card-source .ref {{
            font-weight: 500;
            color: var(--accent);
            padding: 0.1rem 0.5rem;
            background: linear-gradient(135deg, #fff5f5, #fed7d7);
            border-radius: 12px;
            font-size: 0.8rem;
        }}

        .card-lines {{
            flex: 1;
        }}

        .card-lines p {{
            font-size: 1.05rem;
            line-height: 1.85;
            margin-bottom: 0;
            padding-left: 0.25rem;
            border-left: 2px solid transparent;
            transition: border-color .15s;
        }}

        .card-lines p:hover {{
            border-left-color: var(--accent-light);
        }}

        .card-error {{
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            color: var(--text-muted);
            font-style: italic;
            padding: 1rem 0;
        }}

        .card-notes {{
            font-family: 'Inter', sans-serif;
            font-size: 0.8rem;
            color: var(--text-muted);
            background: #f7fafc;
            border-left: 3px solid var(--border);
            padding: 0.5rem 0.75rem;
            border-radius: 0 6px 6px 0;
        }}

        .notes-label {{
            font-weight: 500;
            color: var(--text-light);
        }}

        .dimmed {{
            color: var(--text-muted);
            opacity: 0.5;
        }}

        /* --- Image --- */

        .card-image {{
            width: 100%;
        }}

        .card-image img {{
            width: 100%;
            height: auto;
            display: block;
            cursor: zoom-in;
        }}

        .card-image img.zoomed {{
            position: fixed;
            top: 0; left: 0;
            width: 100vw;
            height: 100vh;
            object-fit: contain;
            background: rgba(0,0,0,.92);
            z-index: 1000;
            cursor: zoom-out;
            border-radius: 0;
        }}

        .no-image {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            min-height: 120px;
            color: var(--text-muted);
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
        }}

        /* --- Navigation --- */

        .jump-nav {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 0.35rem;
            margin-bottom: 2rem;
            padding: 1rem;
            background: var(--card-bg);
            border-radius: 8px;
            box-shadow: var(--shadow);
        }}

        .jump-nav a {{
            font-family: 'Inter', sans-serif;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--primary);
            text-decoration: none;
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            transition: all 0.2s ease;
            border: 1px solid var(--border);
        }}

        .jump-nav a:hover {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        /* --- Footer --- */

        footer {{
            text-align: center;
            margin-top: 4rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            color: var(--text-light);
        }}

        /* --- Responsive --- */

        @media (max-width: 768px) {{
            .card {{
                grid-template-columns: 1fr;
            }}
            .card-col-image {{
                order: 2;
            }}
            header h1 {{
                font-size: 2rem;
            }}
            .card-col-text {{
                padding: 1.25rem;
            }}
            .sort-number {{
                font-size: 1.4rem;
                min-width: 2.25rem;
                height: 2.25rem;
            }}
        }}

        @media print {{
            body {{
                padding: 0;
                background: white;
            }}
            .card {{
                break-inside: avoid;
                box-shadow: none;
                border: 1px solid var(--border);
                margin-bottom: 1rem;
            }}
            .card:hover {{
                transform: none;
                box-shadow: none;
            }}
            .jump-nav {{ display: none; }}
            header {{ margin-bottom: 2rem; padding-bottom: 1rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Card Transcriptions</h1>
            <p class="subtitle">OCR Transcriptions of Scholar Index Cards</p>
            <div class="stats">
                <div class="stat">
                    <span class="stat-number">{total}</span>
                    <span>cards</span>
                </div>
                <div class="stat">
                    <span class="stat-number">{sort_field}</span>
                    <span>sort field</span>
                </div>
            </div>
        </header>

        <nav class="jump-nav">
            {" ".join(f'<a href="#card-{i+1}">{esc(nav_label(c))}</a>' for i, c in enumerate(cards))}
        </nav>

        <main>
            {cards_html}
        </main>

        <footer>
            <p>Generated from {esc(str(folder))} &middot; {total} transcribed cards</p>
        </footer>
    </div>

    <script>
        document.querySelectorAll('.card-image img').forEach(img => {{
            img.addEventListener('click', () => {{
                img.classList.toggle('zoomed');
            }});
        }});
        document.addEventListener('keydown', e => {{
            if (e.key === 'Escape') {{
                document.querySelectorAll('.card-image img.zoomed').forEach(img => {{
                    img.classList.remove('zoomed');
                }});
            }}
        }});
    </script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an HTML demo from OCR transcription JSONs and card images."
    )
    parser.add_argument("folder", type=Path, help="Folder containing .json and image files")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output HTML file path (default: <folder>/index.html)",
    )
    parser.add_argument(
        "-s", "--sort",
        choices=["primary", "secondary", "tertiary", "filename"],
        default="primary",
        help="Which field to sort by (default: primary)",
    )
    parser.add_argument(
        "--include-blank",
        action="store_true",
        help="Include blank/error cards (skipped by default)",
    )
    args = parser.parse_args()

    folder = args.folder.resolve()
    if not folder.is_dir():
        sys.exit(f"Error: {folder} is not a directory")

    print(f"Loading cards from {folder} ...")
    cards = load_cards(folder)
    if not cards:
        sys.exit("No .json transcription files found")

    if not args.include_blank:
        before = len(cards)
        cards = [c for c in cards if not c.get("error_type") and c.get("lines")]
        skipped = before - len(cards)
        if skipped:
            print(f"  Skipped {skipped} blank/error card(s) (use --include-blank to keep)")

    cards.sort(key=lambda c: sort_key(c, args.sort))
    print(f"Loaded {len(cards)} card(s), sorted by {args.sort}")

    out_path = args.output or (folder / "index.html")
    html_content = build_html(cards, folder, args.sort)
    out_path.write_text(html_content, encoding="utf-8")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
