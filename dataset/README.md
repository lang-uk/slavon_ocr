---
license: cc-by-4.0
language:
  - uk
task_categories:
  - image-to-text
tags:
  - ocr
  - handwriting-recognition
  - historical-manuscripts
  - old-ukrainian
  - ruthenian
  - early-modern
  - church-slavonic
pretty_name: Perestoroha OCR
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/train-00000-of-00001.parquet
      - split: validation
        path: data/validation-00000-of-00001.parquet
      - split: test
        path: data/test-00000-of-00001.parquet
---

# Perestoroha OCR

Handwritten index cards containing a 20th-century scholarly transcription of the early 17th-century Ukrainian polemical text *Perestoroha* (Пересторога) by Iov Boretskyi (Lviv, 1605–1606). The cards preserve Old Ukrainian / Ruthenian orthography with archaic diacritics, historical letters (ѣ, ѳ, ѵ), and the source's distinctive line-by-line layout. Each record pairs a 300 DPI card image with line-aligned ground-truth text.

This dataset accompanies the paper *"Digitizing Old Ukrainian Texts: A Prompt-Based OCR Pipeline and Evaluation Dataset"* (Chaplynskyi & Dydyk-Meush, 2026) and the companion code repository at <https://github.com/lang-uk/slavon_ocr>.

## Quick start

```python
from datasets import load_dataset

ds = load_dataset("lang-uk/perestoroha-ocr")
print(ds)
# DatasetDict({train: 278, validation: 122, test: 30})

example = ds["test"][0]
example["image"]            # PIL.Image — 300 DPI JPEG, upright
example["transcription"]    # str — proofread text, line breaks preserved
example["source_reference"] # str — e.g. "Перест. 26."
```

## Splits

| Split | Cards | Provenance |
|---|---:|---|
| `train` | 278 | Cards 153–460 — proofread later; transcribed with Claude Opus 4.7 (xhigh thinking) + the final prompt iteration |
| `validation` | 122 | The 122-card dev split used for prompt iteration (see paper §6). First-batch cards (Opus 4.6 + early prompt). |
| `test` | 30 | The 30-card held-out test split used for final evaluation (paper §5.3). First-batch cards (Opus 4.6 + early prompt). |

The test/validation cards were drawn from the first ~152 proofread cards using a deterministic CER-stratified bucketing (seed=0). The train split is the remainder of the proofread corpus and was *not* used for any model selection in the paper — it's released as supplementary high-quality OCR training data.

## Schema

| Field | Type | Description |
|---|---|---|
| `id` | string | Card identifier, e.g. `Auto-Color0002/001` |
| `image` | Image | 300 DPI JPEG, EXIF orientation already applied (cards are upright) |
| `transcription` | string | Proofread Old Ukrainian text. `\r\n` (CRLF) line breaks preserved for image-text alignment. The final line is the editorial source annotation (e.g. `Львів, 1605-1606, Перест. 38`) written by the 20th-century researcher who made the card; the `source_city` / `source_date` / `source_reference` fields are parsed equivalents. Strip the trailing source line if you need just the *Perestoroha* text. |
| `card_num_primary` | string \| null | Primary card number on the index card |
| `card_num_secondary` | string \| null | Secondary number where present |
| `card_num_tertiary` | string \| null | Tertiary number where present |
| `card_num_notes` | string \| null | Free-text proofreader notes on the numbering scheme |
| `source_city` | string \| null | Manuscript provenance city (typically `Львів`) |
| `source_date` | string \| null | Manuscript date (typically `1605-1606`) |
| `source_reference` | string \| null | Source-line reference (typically `Перест. NN`) |
| `notes` | string \| null | Proofreader notes about textual uncertainty |
| `reviewed_at` | string | ISO-8601 UTC timestamp of proofreading |

## Orthographic conventions

The transcriptions preserve the source manuscript's orthography as faithfully as practical, *except*:

- **Titlo abbreviations are silently expanded** to full orthography. Nomina sacra and other commonly abbreviated words (Богъ, Христосъ, святый, патріархъ, etc.) appear in full form rather than as titlo-marked contractions.
- **No combining diacritics** are used. The single occurrence of a combining macron (card 441) is an isolated exception.
- **Editorial brackets** mark restored or interpolated text: `‹ ›` for editor-supplied passages.

Historical letters retained:

- **ѣ** (yat) — 899 occurrences
- **ѳ** (fita) — 9 occurrences (only in Greek-derived spellings: каѳолическоє, Тимоѳей, Маѳ., Коринѳу)
- **ѵ** (izhitsa) — 2 occurrences (only in еѵангелію)
- **ү** (U+04AF) — 28 occurrences, used distinctly from `у` to mark a specific handwritten glyph variant

## Source material

The cards were produced by 20th-century researchers at the I. Krypiakevych Institute of Ukrainian Studies of the National Academy of Sciences of Ukraine. Each card excerpts a passage of the 1605–1606 *Perestoroha* manuscript and annotates it with provenance metadata. The cards are part of an extended lexicographic project on the language of early modern Ukrainian polemical literature.

The source text — *Perestoroha* itself — is in the public domain (composed 1605–1606). The transcriptions on the cards are 20th-century scholarly work; ground-truth proofreading (2026) is the editorial contribution of the paper authors.

## License

Released under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). If you use this dataset, please cite the paper below.

## Citation

```bibtex
@inproceedings{chaplynskyi-dydyk-meush-2026-perestoroha,
  title     = {Digitizing Old Ukrainian Texts: A Prompt-Based {OCR} Pipeline and Evaluation Dataset},
  author    = {Chaplynskyi, Dmytro and Dydyk-Meush, Hanna},
  year      = {2026},
  note      = {Companion repository: \url{https://github.com/lang-uk/slavon_ocr}}
}
```

## Acknowledgements

We thank the I. Krypiakevych Institute of Ukrainian Studies for access to the source card collection.
