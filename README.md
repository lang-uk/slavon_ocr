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

<!-- citekit:start -->
## Як цитувати

Якщо ви використовуєте **slavon_ocr: OCR for Old Ukrainian handwritten cards**, будь ласка, процитуйте статтю, а не посилання на репозиторій — це єдиний спосіб, у який внесок стає видимим у наукометрії.

> Chaplynskyi, D. and Dydyk-Meush, H. (2026). Digitizing Old Ukrainian Texts: A Prompt-Based OCR Pipeline and Evaluation Dataset. In Proceedings of the Fifth Ukrainian Natural Language Processing Conference (UNLP 2026), pages 58–66. Association for Computational Linguistics. https://aclanthology.org/2026.unlp-1.7/

```bibtex
@inproceedings{chaplynskyi-dydyk-meush-2026-digitizing,
    title     = "Digitizing Old {U}krainian Texts: A Prompt-Based {OCR} Pipeline and Evaluation Dataset",
    author    = "Chaplynskyi, Dmytro and
      Dydyk-Meush, Hanna",
    editor    = "Romanyshyn, Mariana",
    booktitle = "Proceedings of the Fifth {U}krainian Natural Language Processing Conference ({UNLP} 2026)",
    month     = may,
    year      = "2026",
    address   = "Lviv, Ukraine",
    publisher = "Association for Computational Linguistics",
    url       = "https://aclanthology.org/2026.unlp-1.7/",
    pages     = "58--66",
    ISBN      = "979-8-89176-359-3"
}
```
<!-- citekit:end -->
