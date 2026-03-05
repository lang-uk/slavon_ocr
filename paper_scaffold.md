Got it. Here's the updated structure:

---

**Title (working):**
*Digitizing a Historical Ukrainian Manuscript: A Prompt-Based OCR Pipeline, Open-Source Replication, and Evaluation Dataset*

---

**Abstract**

We present a methodology and open dataset for OCR of handwritten index cards constituting a single historical artifact — a scholarly transcription of an Old Ukrainian text from the 16th–17th century. Almost 400 cards, produced by researchers, preserve the full text of one chronicle and contain archaic orthography, titlos, superscript letters, ligatures, and other features of Church Slavonic-influenced writing that make automated recognition non-trivial. We develop a prompt-based OCR pipeline with a custom instruction set, evaluated in two configurations: using Claude Opus via API, and using Qwen running locally on a consumer grade GPU — with identical instructions and the same evaluation data. Evaluated against human-proofread ground truth, the pipelines achieve Character Error Rates of X% and Y% respectively. We release the fully digitized text of the complete artifact — approximately 400 cards — aligned at the line level to 300 DPI scanned images, serving both as a digitized scholarly resource and as training data for future OCR systems targeting historical Slavic manuscripts.

---

**1. Introduction**

- The problem: vast amounts of historical Ukrainian linguistic material exist only in handwritten form, inaccessible to computational methods
- The specific artifact: a set of index cards created by researchers, each reproducing a fragment of a single Old Ukrainian chronicle with source attribution — one complete scholarly transcription of one book
- Why OCR is hard here: archaic script, diacritics (titlos, acutes, superscripts), ligatures, abbreviation marks, inconsistent handwriting, degraded paper
- What we do: build a practical, reproducible pipeline; evaluate it in both a proprietary and a fully open-source configuration; release the result as an open dataset
- Paper structure overview

---

**2. The Artifact**

- Physical description: ~400 cards, all from a single artifact (one chronicle), handwritten, scanned at 300 DPI
- Linguistic content: a complete (or near-complete) scholarly transcription of one Old Ukrainian / Church Slavonic text, 16th–17th century, with source attributions noting library, approximate date, and folio references
- The script: key orthographic features — ѣ, ѡ, ї, titlo (҃), superscript letters in parentheses convention, acute stress marks, abbreviated words
- Why this collection matters: it encodes scholarly decisions about transcription, dating, and attribution — not just raw text. Also it is kind of accessable, where the original text is not.
- Note on scope: this paper covers one complete artifact; experiments on additional artifacts from similar epochs with different orthographic conventions are ongoing (and look promising) and left for future work

---

**3. OCR Pipeline**

- Overview: scanned card image → instruction-driven multimodal LLM → structured text output
- The instruction set (`ocr.md`): iterative development; what it specifies — diacritic handling, superscript notation convention (e.g. КГДЫ(Ж)), titlo representation, ligatures, source line format
- Input: 300 DPI card scans
- Output: transcribed text preserving all orthographic features plus source attribution line
- Two configurations evaluated:
  - **Claude Opus** (API) — the primary setup used to produce the full transcription
  - **Qwen** (local, home server) — fully open-source replication using identical instructions and evaluation data
- Practical details: processing time per card, total throughput, cost considerations

---

**4. Evaluation**

- Ground truth construction: proofreading UI (built with Claude Code) used by a domain expert; N cards proofread out of ~400
- Metrics: Character Error Rate (CER), Word Error Rate (WER); brief note on why both matter for this script
- Results: CER and WER for Claude Opus vs. Qwen — side-by-side comparison
- Error analysis: most common error types — diacritics missed or misplaced, archaic letters confused, titlo expansions, superscript letters
- Qualitative note: expert assessment of overall quality and practical utility

---

**5. Dataset**

- What we release: full transcription of ~400 cards, aligned at line level to 300 DPI images
- Format: JSON + image pairs. TEI XML is planned for too.
- Two use cases: (1) historical linguistic resource — searchable, citable text of the artifact; (2) OCR training/evaluation data for historical Slavic handwriting
- License, availability, DOI

---

**6. Discussion**

- What worked well: instruction engineering as a lightweight, accessible alternative to model fine-tuning
- Open-source viability: what Qwen's results mean practically — can this pipeline run entirely without proprietary APIs?
- Limitations: different epochs and different notation styles (from different scholars) require customisation of prompts. LLM tends to hallucinate some characters or replace some words with more familiar, yet the amount of such errors are small and can be easily fixed during proof-reading.
- Broader implications for digitization of historical Ukrainian manuscript collections

---

**7. Conclusion and Future Work**

- Summary of contributions: pipeline + open-source replication, evaluation, dataset
- Future work: extend to additional artifacts with different orthographic conventions; fine-tune an open-source model on the released dataset; build a lexicographic resource from the digitized text

---

**Acknowledgements, References**
Claude Code.

