Process exactly ONE pending eval card.

This is the in-CC OCR eval loop. It processes a fixed sample (e.g. the 30-card test split or the 122-card dev split) and writes outputs into a run-isolated directory so `score_run.py` can compute CER/WER. No `cards.db` writes.

Re-firing is handled externally — by `/loop <interval> /ocr_eval_one` (cron mode) — so this skill does NOT call ScheduleWakeup at the end. It just processes one card and returns.

PRE-REQUISITE: set the session to opus + max effort before the first invocation. The subagent inherits the thinking budget.

Hardcoded run config (edit the constants below for a new run):

- `SAMPLE`: `editor/samples/test_split.json`
- `RUN_ID`: `opus47_max_test30`
- `SOURCE_FOLDER`: `Auto-Color0002_oriented`
- `MODEL` (for manifest): `claude-opus-4-7`
- `EFFORT` (for manifest): `max`

---

STEP 1 — pick the next card

Run:
```
python editor/eval_loop.py next --sample editor/samples/test_split.json --run-id opus47_max_test30
```

If the output is empty, the pool is exhausted. Run finalize (STEP 4) and STOP.

Otherwise the output is an absolute image path like `/home/dchaplynskyi/slavon_ocr/output/Auto-Color0002_oriented/011.jpeg`. Capture it as `<IMG>`. The output JSON path is the same dir under `runs/<RUN_ID>/<stem>.json` — capture it as `<OUT>`.

For the example image `/home/dchaplynskyi/slavon_ocr/output/Auto-Color0002_oriented/011.jpeg` and run-id `opus47_max_test30`, `<OUT>` is `/home/dchaplynskyi/slavon_ocr/output/Auto-Color0002_oriented/runs/opus47_max_test30/011.json`.

---

STEP 2 — transcribe via fresh subagent

Spawn one Agent with:
- `subagent_type`: `general-purpose`
- `model`: `opus`
- `description`: `OCR eval card <basename of IMG>`
- `prompt`: the full prompt below (with `<IMG>` and `<OUT>` substituted in)

Subagent prompt template (use verbatim):

> Transcribe one handwritten Пересторога research card. The image is at `<IMG>`. Use the Read tool to view it.
>
> Produce a JSON transcription using the rules in `.claude/commands/perestoroha_ocr_preset.md` (read that file first). Save the JSON to exactly this path: `<OUT>`. Use the Write tool. Create any missing parent directories implicitly via Write — the parent dir already exists, you do not need to mkdir.
>
> When done, reply with exactly the JSON file path you wrote and nothing else.

---

STEP 3 — verify the output landed

Quick sanity check: confirm `<OUT>` exists and parses as JSON. If missing or malformed, report the error to the user and STOP — do not reschedule. We don't want to silently skip an eval card.

End the turn with a one-line status: which card was just transcribed and how many remain. /loop will fire the next tick on its own interval.

---

STEP 4 — finalize (only when the pool is exhausted in STEP 1)

Run:
```
python editor/eval_loop.py finalize --sample editor/samples/test_split.json --run-id opus47_max_test30 --model claude-opus-4-7 --effort max
```

This writes `editor/runs/opus47_max_test30.json` so `score_run.py --run-id opus47_max_test30` works. Then report "Eval pool exhausted, manifest written. Ready to score." and STOP. The user should /loop stop the cron at this point (the loop won't auto-stop on exhaustion).
