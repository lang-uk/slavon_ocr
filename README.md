# slavon_ocr

Pipeline for OCR-ing scanned handwritten research cards — 20th-century scholar's index cards with excerpts from early 17th-century Ukrainian (Ruthenian) sources. Uses Claude Code with custom `/ocr` skill for transcription, preserving archaic Church Slavonic orthography.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### 1. Extract pages from scanned PDFs

```bash
python pdf_to_jpeg.py scanned_pdfs/Auto-Color0002.pdf output/Auto-Color0002
```

### 2. Transcribe cards (requires Claude Code CLI)

Single card:

```bash
claude -p "/ocr @output/Auto-Color0002/001.jpeg"
```

Batch:

```bash
python batch_ocr.py output/Auto-Color0002
python batch_ocr.py output/Auto-Color0002 --force   # re-transcribe existing
python batch_ocr.py output/Auto-Color0002 --limit 10
```

### 3. Build HTML demo

```bash
python build_demo.py output/Auto-Color0002 -s tertiary
python build_demo.py output/Auto-Color0002 -s filename -o demo.html
python build_demo.py output/Auto-Color0002 --include-blank
```

Sort options: `primary`, `secondary`, `tertiary`, `filename`.

Blank/error cards are skipped by default; use `--include-blank` to keep them.

Output is a self-contained HTML file (images referenced via relative paths).
