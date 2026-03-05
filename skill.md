# Project Summary: OCR Pipeline for Historical Ukrainian Index Cards

## Overview

Built a production-ready Claude Code slash command (`/.claude/commands/ocr.md`) for transcribing ~200 handwritten scholarly index cards containing excerpts from early 17th-century Ukrainian (Ruthenian) sources. The pipeline is designed to generate structured JSON output suitable for downstream NLP benchmarking and corpus work.

---

## What We Built

### Primary Deliverable
A `.claude/commands/ocr.md` slash command for Claude Code that:
- Checks for existing output before re-running (idempotent)
- Detects blank cards
- Transcribes preserving exact line structure for image-text alignment
- Outputs structured JSON with card numbers, lines, source metadata
- Includes a self-verification step before saving
- Handles multiple card types (prose chronicle, verse, polemical texts)
- Encodes archaic Church Slavonic/Old Ukrainian orthography precisely

### Secondary Deliverables
- `TASK.md` — full OCR benchmarking specification covering ~10 open-source and VLM models, preprocessing pipeline, evaluation metrics, and execution plan
- Reasoning on stateless vs. stateful Claude Code invocation (stateless preferred — no context carryover between cards)
- `mogrify -auto-orient` recommendation for fixing EXIF rotation metadata

---

## The Source Material

### Card Collection
- **~200 index cards** — 20th-century scholarly hand copying excerpts from early 17th-century Ukrainian sources
- **3 ground truth cards** with matched transcriptions (used to develop and validate encoding conventions)
- **~12,000 words** of transcribed period text (no aligned images — used for character inventory analysis)
- **Key insight from visual inspection:** cards are NOT original manuscripts — they are modern scholarly transcriptions, making the handwriting legible but the orthography deeply archaic

### Sources Represented on Cards
1. **Кройника** ("Кройника то єсть исторїа свѣта на шєсть вѣкόвъ") — Lviv, early 17th c. Primary source, deep Church Slavonic orthography
2. **Сак. Вірші** (Сакович, Вірші) — Kyiv, 1622. Baroque panegyric verse
3. **Берест.** (Пересторога) — Lviv, 1605-1606. Polemical text, more modern orthography

---

## Sources Used to Compose the Encoding Instructions

### 1. The Three Ground Truth Cards (Scan0001.jpg)
Direct visual analysis of the three cards revealed the scholar's actual encoding conventions:
- Parentheses `()` for expanded abbreviations
- U+033E combining double apostrophe above (◌̾) for reduced yer
- Greek ω (not Cyrillic ѿ) for the ot-ligature, written as ω(т)
- ѫ (big yus) and ѧ (little yus) preserved
- ӕ for iotified a
- Acute accent marks on stressed vowels
- ║ for manuscript page breaks
- Source metadata in parentheses at end

### 2. The 12,000-Word Corpus (Кройника_1__виправл__.doc / .txt)
Full character inventory analysis from the corpus revealed:
- **s (Latin s) for zelo** — missed entirely in initial analysis, distinct from з and ѕ
- **ѕ (dze, U+0455)** — also missed, frequent in ѕлόстїй, дрүѕїй etc.
- **ү vs ѹ distribution** — ү dominant in Кройника; ѹ in inflectional endings (word-medial/final)
- **є/е coexistence** — both letters appear on the same card; no default rule applies
- **Ѡ (round omega, U+0460)** for section headers distinct from ω
- **ώ (omega with tonos)** for stressed omega
- **ѯ (ksi), ѳ (fita), ѵ (izhitsa)** — confirmed present in corpus
- **Cyrillic numeral titlo** patterns
- **Titlo on sacra nomina** — full inventory of sacred abbreviations (г҃ъ, бг҃ь, нб҃о, сн҃ъ, etc.)
- **(?) convention** for illegible characters

### 3. Verse Card (Screenshot_2026-03-03_at_00_06_38.png — Сак. Вірші card 25)
Analysis of this card revealed:
- Different source types require different output format (verse lines must be preserved)
- **Спүдєй** (not Сүдєй) — confirmed letter-by-letter reading discipline
- **Слүшнє** (not Слáвнє) — confirmed ү vs а confusion risk
- The model tends to substitute familiar words for unfamiliar archaic ones — led to explicit anti-hallucination instructions and the VERIFY step

### 4. Beresteyska Card (001.jpeg — Пересторога)
Analysis of this card revealed:
- **Three card numbers** (22, 221, 1) in different positions/inks — led to the `card_numbers` schema with primary/secondary/tertiary fields
- **Mixed є/е on a single card** — нѣкоторыє but епископове on the same card
- **No trailing ъ** in some words (под, коронных) — led to explicit "never add ъ" instruction
- **исперва not неперва** — word substitution error caught and documented
- **послушєнством not послушенствомъ** — є/е and trailing ъ errors combined

### 5. UCU Phonology/Orthography Lectures (two PDFs)
**Лекція_1__Вимова_звуків.pdf** and **Лекція_1.pdf** — University course materials on Old Ukrainian/Church Slavonic phonology and orthography. Contributed:

- **Паєрик (±/')**  — apostrophe substituting for omitted ь/ъ: в±сѣхъ = вьсѣхъ. New addition.
- **Камора (†)** — marks soft consonant and distinguishes singular from plural: цáрь (sg.) vs ц†арь (pl.). New addition.
- **Придих/звальник („)** — Greek-origin breathing mark over initial vowels: а„мінь. New addition.
- **у vs ѹ positional rule** — у/ó at word start only; ѹ medial/final. Refined from "check each instance" to a precise rule.
- **щ = [шч], sometimes written шт** — scribe variation note added.
- **» (fita variant)** — can render as [ф] or [т]; either form valid.
- **gg in Greek loanwords** = [нг]: ангелъ not ааглъ.
- **Full alphabet table** — confirmed Unicode assignments for all archaic characters.
- **Numeral dot notation** — dots beside titlo'd letters mark numerals: •з҃• = 7.

---

## Key Design Decisions

### JSON Schema Evolution
- Started with flat `card_number` string
- Evolved to `card_numbers` object with `primary`/`secondary`/`tertiary`/`notes` after discovering cards have multiple numbering systems
- `"lines"` array became universal (prose and verse) after realizing line preservation is needed for image-text alignment in benchmarking
- `"type"` field retained for downstream filtering
- `"notes"` field added for uncertainty flagging

### Anti-Hallucination Measures
Three-pronged approach based on observed failure modes:
1. **Explicit instruction** — "read letter by letter, not word by word"
2. **Concrete examples of each error type** in the VERIFY step (сүнодъ→сыномъ, коронныхъ→коронных, єпископовє→епископове)
3. **No defaults** — є/е and ү/у both flagged as requiring per-instance verification against the card

### Stateless Invocation
Decided against keeping context between cards because:
- Contamination risk: Кройника's є-heavy orthography bleeds into Берест. cards
- Each card is source-independent
- Fresh context = fresh eyes, consistent with the letter-by-letter discipline
- Reproducible: any single card can be re-run in isolation
- Parallelizable: multiple instances can run simultaneously

---

## Open Issues / Next Steps

1. **Baseline CER** — run the command on all ~200 cards, measure against the 3 ground truth cards
2. **Open-source model benchmarking** — per TASK.md: Kraken + Old Cyrillic model, Kansallisarkisto multicentury-htr-model, TrOCR variants, PaddleOCR-VL 1.5, Qwen2.5-VL-3B
3. **Vocabulary post-processing** — fuzzy-match OCR output against the 12k-word corpus as a correction layer
4. **Fine-tuning** — if CER > 10%, fine-tune Kraken on annotated lines from ground truth cards
5. **Паєрик/камора/придих in practice** — not yet seen on the cards examined; confirm whether the scholar uses these marks