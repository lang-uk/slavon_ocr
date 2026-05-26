# Opus 4.7 (xhigh thinking) OCR evaluation on the Пересторога corpus

## Experiment summary

**Goal.** Quantify the impact of moving from Claude Opus 4.6 to Claude Opus 4.7
on the handwritten-card OCR pipeline for the Пересторога research corpus
(Ukrainian / Old Slavonic mixed orthography, ~152 reviewed cards), using the
same prompt and the same source images as previous runs.

**Configuration.**
- Model: `claude-opus-4-7` (1M context build).
- Reasoning effort: `xhigh` (extended thinking, max budget).
- Prompt: `.claude/commands/perestoroha_ocr_preset.md` (unchanged from the
  reference preset used by every other run in the comparison).
- Source images: `output/Auto-Color0002_oriented/` (auto-orientation-corrected
  scans, no extra preprocessing).
- Inference harness: in-CC fresh subagent per card (one card per Agent
  invocation, sequential, model=opus, no parallelism). Run-isolated outputs;
  no writes to the proofreading database.
- Sample: 152-card reviewed-and-cleaned subset of the corpus, split
  `seed=20250101` 80/20 into a 122-card dev split and a 30-card test split.
- Evaluation: micro-averaged CER and WER (flat character / token edit
  distance) against the human-proofread `lines` field, after normalising
  source-reference lines and the same character cleaning used by every other
  run. Tokenisation for WER uses spaCy `uk_core_news_sm` (whitespace and
  punctuation tokens dropped).

**Headline result.**
On the 152-card pooled corpus, Opus 4.7 xhigh achieves **2.51% CER / 12.16%
WER**, compared to the prior best per-prompt configuration on the 30-card test
split (`v5_opus46_max`, opus 4.6 xhigh + v5 prompt) at 3.39% CER / 16.72% WER.
On the 30-card test split alone, 4.7 xhigh measures **2.88% CER / 13.96% WER**,
a ~15% relative CER reduction over the best 4.6 result on the same split with
the same prompt family.

The previous full-corpus prod ingest run (152 cards, also using
`perestoroha_ocr_preset`, but on Opus 4.6 + xhigh; model/effort fields not
recorded in its manifest, see `editor/runs/prod_all152.json`) measured 4.16%
CER / 18.10% WER, putting the 4.6 → 4.7 jump at roughly a 40% relative CER
reduction at corpus scale.

**Residual error structure (dev split, 122 cards).**
The dominant remaining error classes are still orthographic equivalences that
are genuinely ambiguous in 19th-century Ukrainian/Old Slavonic handwriting,
not visual recognition failures:

| Substitution | Count | Note |
|---|---:|---|
| `є → е` | 95 | yat / iotated-e merge |
| `е → є` | 31 | reverse |
| `ъ → ь` | 17 | hard / soft sign |
| `ү → у` | 17 | digamma-like form / u |
| `і → и` | 13 | i-decimal / i |
| `е → ѣ` | 9 | yat |
| `и → ы` | 5 | |
| `о → а` | 4 | |

These account for the bulk of CER and explain why CER moves much more
aggressively than WER: most errors are single-character substitutions inside
otherwise-correct words.

## Comparison tables

### Test split (30 cards, sorted by CER ascending)

| Run | CER | WER | Model · effort · CLI · prompt |
|---|---:|---:|---|
| **opus47_xhigh_test30** | **2.88%** | **13.96%** | claude-opus-4-7 · xhigh · in-cc-agent · `perestoroha_ocr_preset` |
| v5_opus46_max | 3.39% | 16.72% | opus 4.6 · max · `ocr_perest_v5` |
| v6_test | 3.57% | 15.80% | opus 4.6 · `ocr_perest_v6` |
| v5_test | 3.67% | 16.56% | opus 4.6 · `ocr_perest_v5` |
| v5_opus46_high | 4.02% | 18.10% | opus 4.6 · high · `ocr_perest_v5` |
| perest_test | 4.17% | 20.09% | opus 4.6 · `ocr_perest` |
| v7_test | 4.22% | 17.02% | opus 4.6 · `ocr_perest_v7` |
| v5_opus45_med | 4.42% | 20.86% | claude-opus-4-5 · medium · `ocr_perest_v5` |
| glyph_test | 4.45% | 21.93% | `ocr_perest_glyph` |
| v4_test | 4.50% | 22.24% | `ocr_perest_v4` |
| baseline_rot_test | 4.53% | 20.55% | `ocr` (no prompt tuning) |
| perest_test_v2 | 4.73% | 21.17% | `ocr_perest` |
| esrgan2x_test | 4.98% | 23.16% | ESRGAN ×2 preprocessing · `perestoroha_ocr_preset` |
| upscale2x_test | 5.01% | 23.16% | bicubic ×2 preprocessing · `perestoroha_ocr_preset` |
| perest_v2_test | 5.03% | 23.62% | `ocr_perest_v2` |
| codex_gpt54_xhigh_test30 | 5.13% | 24.08% | gpt-5.4 · xhigh · codex CLI · `perestoroha_ocr_preset` |
| v5_sonnet_med | 5.31% | 23.16% | claude-sonnet-4-5 · medium · `ocr_perest_v5` |

### Dev split (122 cards)

Only the new Opus 4.7 xhigh configuration has been run on the full dev split;
earlier model/prompt sweeps used either the 30-card test split or a separate
32-card `sample_0_32.json` slice and are therefore not directly comparable
here.

| Run | CER | WER | Model · effort · CLI · prompt |
|---|---:|---:|---|
| **opus47_xhigh_dev122** | **2.42%** | **11.76%** | claude-opus-4-7 · xhigh · in-cc-agent · `perestoroha_ocr_preset` |

### Full corpus (test + dev pooled = 152 cards)

| Run | n | CER | WER | Notes |
|---|---:|---:|---:|---|
| **opus47_xhigh (test30 + dev122 pooled)** | 152 | **2.51%** | **12.16%** | claude-opus-4-7 · xhigh · this experiment |
| prod_all152 | 152 | 4.16% | 18.10% | older prod ingest using `perestoroha_ocr_preset` (Opus 4.6 era; model/effort not recorded in manifest) |

## Reproducibility / artifact pointers

- Splits definition: `editor/splits.json` (seed 20250101, dev=122, test=30).
- Per-card OCR JSONs:
  - test split — `output/Auto-Color0002_oriented/runs/opus47_xhigh_test30/`
  - dev split — `output/Auto-Color0002_oriented/runs/opus47_xhigh_dev122/`
- Manifests: `editor/runs/opus47_xhigh_test30.json`,
  `editor/runs/opus47_xhigh_dev122.json`.
- Score summaries (per-card CER/WER, top error classes):
  `editor/runs/opus47_xhigh_test30.summary.json`,
  `editor/runs/opus47_xhigh_dev122.summary.json`.
- Scoring code: `editor/score_run.py` (CER + WER, micro-averaged); rerun with
  the project venv: `.venv/bin/python editor/score_run.py --run-id <id>`.
- Reference text: `editor/cards.db`, rows where `reviewed=1 AND deleted=0`.
