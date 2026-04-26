---
name: Analyze error reports after every iteration
description: In OCR prompt iteration, after each run do a substitution/insertion/deletion analysis (not just aggregate CER) before reporting to the user
type: feedback
originSessionId: e2f92c53-854e-4c20-b34a-8c8b0cc0f710
---
After every prompt-iteration run in this project, do a deep error-class analysis BEFORE reporting results. Don't just report aggregate CER — break down:

- Top substitutions (ref→hyp pairs), top insertions, top deletions, ranked by count and by stability across runs
- Per-card error distribution (which cards dominate the budget)
- Which error classes are stable run-to-run (real systematic issues) vs noisy (perceptual/model uncertainty)
- Evidence of label errors or systematic handwriting misreads
- The most striking findings the user should know about

**Why:** Aggregate CER hides the dominant error classes. A concrete example from this project: we spent 4+ iterations chasing є/е substitutions (~86 cases) before noticing that ъ INSERTIONS were 107 cases — the #1 error class — because metrics.py only tracked substitutions. Surfacing the wrong number led to misdirected iterations.

**How to apply:** After every new run (or set of runs), use the editor/metrics.py helper AND a dedicated op-breakdown pass that includes insertions/deletions/per-card concentration. Report the striking findings with evidence (actual context snippets where relevant). Only propose the next candidate after you've identified the biggest actionable lever from the analysis — not based on a hunch.
