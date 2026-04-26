---
name: OCR prompt iteration experiment log
description: Key findings from the 2026-04-11/12 prompt optimization session — what worked, what didn't, noise floor, scoring bugs
type: project
originSessionId: e2f92c53-854e-4c20-b34a-8c8b0cc0f710
---
## Production state (as of 2026-04-12)
- Prompt: `perestoroha_ocr_preset.md` (v7 = v5 + 4 typo fixes)
- Best config: Opus 4.6 default effort, oriented images at native 1150×760
- Full corpus (152 cards): **CER 4.16%, WER 18.10%**
- Test split (30 cards): **CER 3.67%, WER 16.56%**
- Zero banned Кройника letters

## What worked
1. **Source-specialization** (ocr.md → ocr_perest): biggest single lever. Dropping Кройника-only rules + statistical priors for Пересторога conventions. -1.23pp CER on full corpus.
2. **Orientation preprocessing**: 106/431 scanned images had EXIF rotation issues. Auto-orient fix made catastrophic cards (137% CER) readable. One-time preprocessing.
3. **Balanced trailing-ъ sweep** (v5): reduced ъ insertions ~60% without triggering compensatory deletions. Key wording: "both directions are equally wrong, decide by glyph."
4. **"NEVER add a trailing ъ" anchor**: the absolutist language in CRITICAL REMINDERS + ALPHABET section is functionally essential even though it contradicts the balanced sweep. Removing it (v6) caused ъ insertions to triple on dev. Keep it.
5. **Scoring fixes** (3 bugs): source-line strict match → heuristic, multi-line source scan, `...` ↔ `…` normalization. Combined ~1.5pp artificial inflation removed.

## What didn't work
1. **Sharpened є/е glyph rule** (v2, ee1): "require explicit middle bar" pushed model too hard toward plain letters, caused і→и and other regressions. Test split always regressed.
2. **Source-reference VERBATIM rule**: one-sentence prompt addition caused є→е to spike +10 on test. Reverted.
3. **LANCZOS 2× upscaling**: +1.34pp WORSE. Blurry edges, thinking-budget exhaustion (5/30 fallbacks).
4. **Real-ESRGAN 2× super-res**: +1.31pp WORSE. Same thinking-budget issue. Resolution is NOT the bottleneck.
5. **Glyph reference card** (attaching a 0%-CER card as visual reference): є→е improved -6 but е→є worsened +10, ъ insertions +6. Showing BOTH forms of confused pairs increases bidirectional confusion. The statistical bias in the text prompt was more effective than visual examples.
6. **Higher effort on Opus 4.6**: non-monotonic (default 3.67% > high 4.02% < max 3.39%). Within noise; not worth 2.6× cost.
7. **Other models**: Opus 4.5 (+0.75pp worse, 3× slower), Sonnet (+1.64pp worse, different error profile — ы→и systematic).

## Key measurements
- **Noise floor** (same prompt, same images, different runs): ~0.47pp CER on 32-card sample, ~0.13pp within perest family
- **Dominant residual error classes** (full 152-card corpus): ъ insertions (125), є→е subs (109), е→є subs (55), ъ deletions (37)
- **Error budget concentration**: top 10% cards hold 30% of errors; 74% of cards are below 5% CER
- **Per-card CER distribution**: median 3.24%, P25/P75 = 2.05%/5.10%, 17 perfect cards, 6 cards >10%

## Harness/infrastructure built
- `editor/eval_setup.py`: baseline CER from DB, frozen dev/test split
- `editor/sample_dev.py`: stratified sampler (4 buckets × N cards)
- `editor/eval_run.py`: iteration runner with --model, --effort, --reference-image, --parallel, thinking retry
- `editor/score_run.py`: CER scorer with editops
- `editor/compare_runs.py`: tabulate runs
- `editor/metrics.py`: targeted per-class error metrics
- `editor/build_review.py`: HTML review page with image + GT + diff
- `editor/preprocess_orient.py`: EXIF-based auto-orientation
- `.venv/`: Python 3.12 with torch, spandrel, realesrgan, spacy uk_core_news_sm, rapidfuzz, Pillow, anthropic

## Remaining paths to <3% CER
1. **Majority voting** across 3 runs (noise cancellation, ~-0.5-1pp expected)
2. **Lexicon post-correction** from 12k-word corpus (catch word-level hallucinations)
3. **Label audit** of top-50 error cards (some "errors" are label-side, like card 027)
4. **Isolated glyph crops** (not full reference cards) — show ONLY minority-form glyphs
5. **Fine-tuning** a smaller VLM on the 152 card pairs (nuclear option, highest ceiling)
