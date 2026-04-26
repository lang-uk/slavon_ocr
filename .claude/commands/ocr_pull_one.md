Process exactly ONE pending Пересторога card and reschedule yourself.

This is the in-CC OCR pull loop. Each invocation handles one card and uses ScheduleWakeup to fire again ~3 minutes later, until the pool is exhausted. Per-card context isolation comes from spawning a fresh subagent — the main loop's per-tick context stays tiny.

PRE-REQUISITE (set once before invoking the first time):
The subagent inherits its thinking budget from this session. For best OCR quality, set the session to opus + xhigh effort before starting the loop.

---

STEP 1 — pick the next card

Run:
```
python editor/pull_loop.py next
```

If the output is empty, the pool is exhausted. Report "All cards processed." and STOP. Do NOT call ScheduleWakeup.

Otherwise the output is an absolute image path like `/home/dchaplynskyi/slavon_ocr/output/Auto-Color0002_oriented/182.jpeg`. Capture it as `<IMG>`.

---

STEP 2 — transcribe via fresh subagent

Spawn one Agent with:
- `subagent_type`: `general-purpose`
- `model`: `opus`
- `description`: `OCR card <basename of IMG>`
- `prompt`: the full prompt below (with `<IMG>` substituted in)

Subagent prompt template (use verbatim, substituting `<IMG>` with the actual absolute path):

> Transcribe one handwritten Пересторога research card. The image is at `<IMG>`. Use the Read tool to view it.
>
> Produce a JSON transcription using the rules in `.claude/commands/perestoroha_ocr_preset.md` (read that file first). Save the JSON next to the image at the same stem with extension `.json` — i.e. for `<IMG>` ending in `.jpeg`, save to the same path with `.jpeg` replaced by `.json`. Use the Write tool.
>
> When done, reply with exactly the JSON file path you wrote and nothing else.

---

STEP 3 — ingest the result

The subagent returned a JSON path; capture as `<JSON>`. Run:
```
python editor/pull_loop.py ingest <IMG> <JSON>
```

If ingest fails (duplicate row, malformed JSON, etc.), report the error to the user and STOP — do not reschedule. We don't want to silently skip a card or loop on a bug.

---

STEP 4 — reschedule

Call ScheduleWakeup with:
- `delaySeconds`: 180
- `prompt`: `/ocr_pull_one`
- `reason`: `next card in 3 min` (or include the just-ingested filename for traceability)

End the turn with a one-line status: which card was just ingested and how many remain (you can get the remaining count by running `python editor/pull_loop.py next` once more — but that's optional; the count isn't load-bearing).
