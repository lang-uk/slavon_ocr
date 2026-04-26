# Digitizing Historical Ukrainian Texts: A Prompt-Based OCR Pipeline and Evaluation Dataset

**Anonymous submission to UNLP 2026 (short paper)**

---

## Abstract

We present a methodology and an open dataset for OCR of handwritten index cards containing a scholarly transcription of an early 17th-century Ukrainian polemical text, *Perestoroha* by Iov Boretskyi (Lviv, 1605–1606). The 430 cards, produced by 20th-century researchers, preserve the text in Church Slavonic-influenced orthography with archaic diacritics, titlos, superscript letters, and ligatures that make automated recognition non-trivial. We develop a prompt-based OCR pipeline driven by a custom instruction set, designed iteratively from the source material's orthographic conventions. The pipeline is evaluated in two configurations: a proprietary multimodal LLM accessed via API and an open-source model running locally on consumer hardware, both using identical instructions and evaluation data. Against human-proofread ground truth, the two configurations achieve Character Error Rates of **3.4%** and **15.1%**, respectively. We release the fully digitized text aligned at line level to 300 DPI scanned images, as both a scholarly digital resource and training data for future OCR systems targeting historical Slavic manuscripts.

## 1. Introduction

A significant body of Ukrainian historical linguistic material remains accessible only in handwritten form — either as original manuscripts or as scholarly transcriptions produced by researchers over the past century. Digitizing these materials is a prerequisite for computational analysis, full-text search, lexicography, and long-term preservation, yet the archaic orthographic conventions they employ render standard OCR tools ineffective.

We address this problem for a specific artifact: a set of 430 handwritten index cards constituting a scholarly transcription of *Пересторога зѣло потребная на потомные часы православнымъ христіаномъ* (*Perestoroha zelo potrebnaia na potomnye chasy pravoslavnym khrystiianom*), a polemical text by Iov Boretskyi written in Lviv in 1605–1606. The cards were produced by 20th-century researchers who carefully reproduced the original text, preserving its Church Slavonic-influenced orthography, titlo abbreviation marks, superscript letters, and other diacritical features.

Rather than fine-tuning a dedicated handwritten text recognition model — which would require substantial annotated training data — we adopt a **prompt engineering** approach: we develop a detailed instruction set that guides a multimodal large language model to transcribe each card image into structured text while preserving all orthographic features. The instruction set was developed iteratively for Claude Opus 4.6 through analysis of the source material's character inventory, abbreviation conventions, and diacritic usage patterns. We then evaluate the same instruction set with Qwen3.5-35B as an open-source replication.

Our contributions are: (1) a practical, reproducible prompt-based OCR pipeline for historical Ukrainian handwriting, evaluated in both a proprietary and a fully open-source configuration; and (2) an open dataset of 430 card transcriptions aligned to high-resolution scans.

<!-- TODO: Add a Related Work section (comment #5/#6/#7). Postponed for now. -->

## 2. The Perestoroha Image Dataset

The source material consists of 430 index cards, scanned at 300 DPI, all belonging to a single scholarly artifact. Each card reproduces a fragment of *Perestoroha* with source attribution noting library provenance, approximate date, and folio references. The cards were handwritten by 20th-century researchers, making the handwriting itself relatively legible; the difficulty lies in the orthographic system being reproduced.

The text employs Church Slavonic-influenced Ukrainian orthography of the early 17th century. Key features include: **ѣ** (yat), **ω** (omega as ot-ligature, rendered *ω(т)* in the scholar's convention), **ї** (yi with two dots), **ѫ** (big yus) and **ѧ** (little yus); **titlo** marks over abbreviated sacra nomina (e.g., *г҃ъ* for *господь*, *бг҃ъ* for *богъ*); superscript letters indicating abbreviation expansions; acute stress marks on vowels; and the coexistence of **є** and **е**, **ү** and **у** — visually similar pairs that require per-instance discrimination rather than any default substitution rule.

The cards employ multiple numbering systems (primary, secondary, and occasionally tertiary numbers in different inks and positions), reflecting successive cataloguing efforts. Source metadata — provenance, date, and folio number — appears at the end of each card. The original manuscript is difficult to access; the index cards, now digitized, provide a practical point of entry for both computational and traditional scholarship.

<!-- TODO: Add a figure showing an example card with annotated features (titlo, superscript, ѣ, etc.) -->

## 3. OCR Pipeline

### 3.1 Overview

The pipeline consists of four stages: (1) splitting scanned PDF files into individual card images; (2) instruction-driven multimodal LLM transcription of each image into structured JSON; (3) import into a web-based proofreading editor for expert review; and (4) export of corrected transcriptions into a browsable dataset. Each card is transcribed independently — no context carries over between cards — ensuring reproducibility and enabling parallel processing. The code is available at <link_placeholder>.

<!-- TODO: if space permits, add a pipeline diagram figure (comment #11) -->

### 3.2 The Instruction Set

The core of the pipeline is a custom instruction set (`ocr.md`) for Claude Opus 4.6, developed iteratively over multiple rounds of analysis and error correction. Its design drew on several sources:

- **Three ground-truth cards** with matched manual transcriptions, which revealed the scholar's encoding conventions: parentheses for expanded abbreviations, U+033E (combining double apostrophe above) for reduced yer, Greek ω (not Cyrillic ѿ) for the ot-ligature, and specific diacritical mark usage.
- **A 12,000-word reference corpus** of the same text (already digitized, provided by a co-author), which yielded a full character inventory. This analysis uncovered characters initially missed — Latin *s* for zelo (distinct from *з* and *ѕ*), the positional distribution of *ү* vs *ѹ*, and a complete inventory of titlo'd sacra nomina.
- **Lecture materials** on Old Ukrainian/Church Slavonic phonology and orthography from a Ukrainian research institute, which contributed precise descriptions of rarely encountered marks: paieryk (apostrophe substituting for omitted ь/ъ), kamora (marking soft consonants), and prydykh (Greek-origin breathing mark over initial vowels).
- **Additional card types** (verse, polemical text) that exposed the need for format-specific handling and revealed systematic word-substitution errors where the model replaced unfamiliar archaic forms with visually similar modern words.

The instruction set specifies a detailed character encoding table with Unicode codepoints, rules for diacritic handling (titlo, acute, superscript letters), the convention for representing abbreviation expansions (letters in parentheses, e.g., *в̾ши(т)ко*), source line format, and a structured JSON output schema with fields for card numbers (primary/secondary/tertiary), transcribed lines, source metadata, and uncertainty notes. Key components — the character encoding table, the verification step, and the JSON output schema — are provided in Appendix A. <!-- TODO: create appendix (comment #14) -->

### 3.3 Anti-Hallucination Measures

Early experiments revealed a critical failure mode: the model tends to substitute familiar words for unfamiliar archaic ones, especially when letter shapes are ambiguous. For example, *Спүдєй* was misread as *Сүдєй*, and *исперва* as *неперва* — plausible-looking modern forms replacing rare historical ones.

We adopted a three-pronged mitigation strategy: (1) explicit "read letter by letter, not word by word" instructions; (2) a verification step listing concrete examples of documented error types (є/е confusion, ү/у substitution, spurious trailing *ъ*); and (3) a "no defaults" policy — both members of each visually similar pair (є/е, ү/у) are flagged as requiring per-instance verification against the card image.

### 3.4 Thinking Spiral Mitigation

With extended thinking (chain-of-thought reasoning) enabled, we observed a failure mode in which the model entered an unbounded deliberation loop on cards with many ambiguous characters, consuming its entire output token budget without producing any transcription. This occurred consistently across multiple attempts with token limits of 4K and 32K.

The root cause is that extended thinking expands to fill whatever budget is available, and the instruction set's emphasis on precision amplifies this tendency. Completely disabling extended thinking for OCR runs resolved the issue. A prompt-level mitigation — a "deliberation discipline" section instructing the model to make one pass, verify once, and commit — proved helpful but insufficient on its own.

### 3.5 Proofreading Editor

We built a custom web-based proofreading editor (Flask + SQLite) using Claude Code. The editor displays the scanned card image alongside the model's transcription in a side-by-side view, with a toolbar for inserting Church Slavonic diacritics and archaic characters (ѣ, ѫ, ѧ, titlo, etc.), enabling a domain expert to correct errors character by character. Corrected transcriptions are exported as parallel JSON files, preserving the original OCR output for comparison.

Proofreading was performed by a co-author with domain expertise in historical Ukrainian linguistics. A total of **152** cards were proofread. The annotator's familiarity with the source material's orthographic system was sufficient to resolve ambiguities without formal adjudication guidelines.

## 4. Evaluation

### 4.1 Experimental Setup

We evaluate the pipeline in two configurations using identical instructions and evaluation data:

- **Claude Opus 4.6** (proprietary, API access) — the primary setup used to transcribe all 430 cards. <!-- TODO: add reference (comment #19) -->
- **Qwen3.5-35B** (open-source, running locally on a consumer-grade GPU) — a fully open-source replication using the same instruction set without modification. <!-- TODO: add reference (comment #20), fill in GPU specs, inference time per card, cost comparison -->

### 4.2 Metrics

We report Character Error Rate (CER) and Word Error Rate (WER). CER is the primary metric, as word boundaries in this orthographic system are not always unambiguous, and many errors involve single-character substitutions within diacritical marks. Tokenization for WER was performed using the spaCy NLP pipeline for Ukrainian.

### 4.3 Results

| Configuration | Cards | CER (%) | WER (%) |
|:---|:---:|:---:|:---:|
| Claude Opus 4.6 (API) | 145 | 3.4 | 16.9 |
| Qwen3.5-35B (local) | 143 | 15.1 | 40.6 |

### 4.4 Error Analysis

Character-level edit operations for Claude Opus 4.6 on the 145-card evaluation set comprise 504 substitutions, 136 insertions, and 70 deletions (710 total edits over ~21,000 reference characters). The most frequent error categories are:

1. **є/е confusion** (U+0454 ↔ U+0435) — 223 substitutions in both directions, accounting for 44% of all substitutions. This reflects genuine visual ambiguity in the scholar's handwriting, where the two glyphs differ by a single stroke.
2. **ы/и substitution** — 36 cases where the model reads historical *ы* as modern Ukrainian *и*, consistent with the model's bias toward contemporary orthography.
3. **Spurious *ъ* insertion** — 63 inserted hard signs, the single largest insertion category. The model over-applies the convention of word-final *ъ*, adding it where the source text omits it.
4. **я/ѧ confusion** — 15 cases. The model substitutes archaic little yus (ѧ) for modern *я* or vice versa.
5. **ѣ (yat) misreadings** — 32 substitutions across multiple confusions (ѣ→ъ, ѣ→і, ѣ→ы, ѣ→ь), reflecting the visual similarity of yat to several other characters in this handwriting.

**Qwen-specific patterns.** Qwen3.5-35B exhibits the same є/е and ы/и confusions as Claude but at higher rates, alongside error types largely absent from the Claude output. Notably, Qwen produces severe whole-word hallucinations on a substantial fraction of cards: on approximately 15% of evaluation cards, the model generates text bearing little resemblance to the source, with per-card CER exceeding 50%. These are not character-level misreadings but wholesale fabrications — the model appears to "narrate" plausible-looking Church Slavonic text rather than transcribing what is on the card. Additional frequent Qwen errors include ъ/ь confusion (44 cases), т/м substitution (37 cases), and systematic ү→у merging (24 cases). However, this comparison may not be entirely fair: the instruction set was developed and iteratively refined for Claude Opus 4.6, then applied to Qwen without modification. Moreover, the Qwen configuration used a quantized model (Qwen3.5-35B-A3B-UD-MXFP4_MOE.gguf), which may further degrade fine-grained character discrimination. Prompt tuning specifically for the open-source model, or using a less aggressively quantized variant, could plausibly reduce the hallucination rate.

Given the diversity of error types and the many legitimate rare forms in this script, automated post-processing (e.g., rule-based correction or fuzzy matching) risks introducing new errors. Manual proofreading by a domain expert using the editor described in Section 3.5 remains the most reliable correction method.

## 5. Dataset

We release the fully digitized text of *Perestoroha* as transcribed from 430 index cards. The dataset consists of JSON files paired with 300 DPI card images, aligned at line level. Each JSON record contains card numbers (primary, secondary, and tertiary where present), an array of transcribed lines preserving exact line breaks for image-text alignment, source metadata (provenance, date, folio), and free-text notes flagging uncertainty.

The dataset serves two purposes: (1) as a **historical linguistic resource** — a searchable, citable digital text of a significant early 17th-century Ukrainian source that is otherwise difficult to access; and (2) as **OCR training and evaluation data** for future systems targeting historical Slavic handwriting.

<!-- TODO: specify license, availability (Hugging Face / GitHub), DOI if available, mention planned TEI XML version -->

## 6. Discussion

**Prompt engineering as a lightweight alternative to fine-tuning.** The instruction set — approximately 3,000 words of encoding rules and error mitigation — required no training data beyond a few reference cards and a character inventory corpus. This makes the approach accessible to digital humanities practitioners who lack the resources for model fine-tuning.

**Open-source viability.** The Qwen3.5-35B configuration achieves a CER of 15.1% using the same instruction set without modification — roughly 4.5× higher than Claude's 3.4%. While this is too high for unsupervised digitization, it may still be useful as a first pass that reduces manual transcription effort, particularly for institutions that cannot use proprietary APIs. The performance gap is driven primarily by whole-word hallucinations (Section 4.4), suggesting that instruction-set adaptations specifically targeting the open-source model — or fine-tuning on the released dataset — could substantially close the gap.

**Broader implications.** Ukrainian archives hold substantial collections of handwritten linguistic material from the 16th–18th centuries. The prompt-based approach demonstrated here can be adapted to other artifacts by developing source-specific instruction sets, potentially enabling large-scale digitization without the overhead of training dedicated models for each orthographic convention.

## 7. Conclusion

We presented a prompt-based OCR pipeline for digitizing handwritten scholarly index cards containing a 17th-century Ukrainian text. The pipeline, driven by a carefully engineered instruction set, achieves a CER of 3.4% with a proprietary model and 15.1% with an open-source alternative. We release the fully digitized text of *Perestoroha* — 430 cards aligned to scanned images — as an open resource for historical linguistics and OCR research.

Future work includes extending the pipeline to additional artifacts with different orthographic conventions (experiments are underway and show promising results), fine-tuning an open-source model on the released dataset, and building a searchable lexicographic resource from the digitized text.

## Limitations

The pipeline was developed and evaluated on a single artifact with a specific orthographic system. Generalization to other historical Ukrainian texts — particularly those from different centuries or with different transcription conventions — requires partial re-engineering of the instruction set. The ground truth was produced by a single domain expert, and inter-annotator agreement has not been measured. The proprietary configuration (Claude Opus) incurs API costs that may be prohibitive for large-scale digitization; the open-source alternative (Qwen) offers a cost-free option but at substantially lower accuracy (CER 15.1% vs 3.4%), with frequent whole-word hallucinations limiting its utility without expert proofreading.

## Ethical Considerations

This work involves digitization of historical scholarly materials in the public domain. No personal or sensitive data is processed. We used AI-based writing assistance tools (Claude) in preparing this manuscript, as well as Claude Code for developing the OCR pipeline and the proofreading interface. The open-source release of the dataset and instruction set is intended to enable reproducibility and further research.

## Acknowledgements

<!-- TODO -->

## References

<!-- TODO: compile bibliography -->
