Transcribe the handwritten research card in the provided image.

These are 20th-century scholar's index cards copying excerpts from Пересторога (Lviv, 1605-1606) — a Ukrainian polemical text. Orthography is early Ukrainian, NOT deep Church Slavonic: most archaic Кройника features are ABSENT. Transcribe what the card actually shows.

---

STEP 1 — PREPROCESSING:

1. If a .json file with the same name already exists next to the image, SKIP and report "already transcribed" unless --force is passed.
2. If the card is blank or contains only smudges, output the blank-error JSON (see schema).

---

STEP 2 — TRANSCRIBE:

Read each letter INDIVIDUALLY, character by character. Do NOT guess words by overall shape. Do NOT substitute a modern Ukrainian spelling for what is actually written. Preserve the card's line structure exactly: each handwritten line becomes one entry in "lines", even within verses or prose.

---

STEP 3 — VERIFY BEFORE SAVING:

Re-read the image and check for:
- INSERTED LETTERS: characters added that aren't on the card (e.g. writing подъ when card shows под — trailing ъ not there)
- SUBSTITUTED WORDS: a familiar word replacing an unfamiliar one (e.g. сүнодъ instead of сыномъ, неперва instead of исперва)
- MISSING CHARACTERS: letters skipped

Then do a dedicated є/е SWEEP — this is the single most frequent error class on Пересторога:
1. Find every е or є in your transcription.
2. Look at the handwritten glyph on the card for each one.
3. Decide by SHAPE:
   - є (U+0454): like a backwards C with a horizontal middle bar — opening faces RIGHT, resembles an upside-down 3.
   - е (U+0435): a modern "e" — closed loop with opening on the LEFT.
4. On Пересторога cards, plain е is ~3-4× more common than є. When the glyph is genuinely ambiguous, write е.
5. NEVER decide by word priors ("which looks more like modern Ukrainian"). The same card can have both letters in neighboring words (нѣкоторыє but епископове). Modern spelling intuitions are a TRAP.

Same logic for и vs і: plain и is ~4× more common. Only write і when you clearly see a dotted i on the card. Never write ї — Пересторога cards do not use the iotified-i form.

Then do a dedicated TRAILING-ъ SWEEP — the single largest error class on Пересторога:

Word-final ъ (hard sign after a consonant) in Пересторога is MIXED: some words have it, others don't, and the only way to decide is glyph inspection. Both directions are errors — inserting a ъ that isn't there and dropping one that is there are equally wrong.

1. For every word ending in a hard consonant (д, т, с, н, р, м, л, к, х, в, п, б, г, ж, з), look at the handwritten glyph at word end.
2. Distinguish by stroke visibility:
   - A clear separate ъ stalk (short vertical stroke with a small bowl, attached after the final consonant) → write ъ.
   - A plain consonant followed by space/punctuation with no extra stalk → omit ъ.
3. A natural flourish on the final consonant (ж, д, т, ъ, у, etc.) is NOT a ъ. The ъ is a DISTINCT separate stroke with its own structure.
4. Do not let a "this text looks archaic, so it needs ъ" reflex override the glyph. Both forms coexist in this source in roughly equal proportions.
5. Equally: do not drop ъ prophylactically. If the glyph is there, write it.
6. Reference examples of both shapes in the proofread corpus:
   - WITHOUT trailing ъ: иж, обычаєм, Книг, оных, самодержцов, наукам, руских, так, чим
   - WITH trailing ъ: былъ, наступилъ, въ, прєдъ, потомъ, господаръ

If you find errors, fix them before saving. When a character is genuinely ambiguous after looking at the glyph, write your best reading and flag the word in "notes".

---

STEP 4 — SAVE OUTPUT:

Save a JSON file next to the source image with the same stem and .json extension.
Example: @data/001.jpeg → data/001.json

---

JSON SCHEMA — successful transcription:
```json
{
  "filename": "001.jpeg",
  "card_numbers": {
    "primary": "22",
    "secondary": "221",
    "tertiary": "1",
    "notes": "22 top-left pencil, 221 top-center ink, 1 bottom-right corner"
  },
  "lines": [
    "Пересторога зѣло потребная на по-",
    "томныє часы православнымъ христіанамъ,",
    "святое каѳолическое восточное церкве",
    "сыномъ, абы вѣдали, яко нѣкоторыє епи-",
    "скопове панствъ коронных, которыє испер-",
    "ва под владзою и под послушєнством",
    "святѣйшаго вселенскаго константино-",
    "полскаго патріархи были",
    "Львів, 1605-1606, Перест. 25."
  ],
  "source": {
    "city": "Львів",
    "date": "1605-1606",
    "reference": "Перест. 25."
  },
  "notes": ""
}
```

JSON SCHEMA — blank/illegible card:
```json
{
  "filename": "001.jpeg",
  "card_numbers": {"primary": null, "secondary": null, "tertiary": null, "notes": ""},
  "lines": null,
  "source": null,
  "notes": "Description of the problem",
  "error_type": "blank | illegible"
}
```

CARD NUMBERS: cards often have multiple numbers in different positions/inks. Capture ALL of them:
- "primary": the scholar's sequence number (often top-left, pencil)
- "secondary": catalog/inventory number (often top-center, different ink)
- "tertiary": any additional number (bottom corner, margin)
- "notes": describe position and appearance of each. Set unused fields to null.

---

ORTHOGRAPHY — Пересторога-specific

ALPHABET PRESENT on these cards (transcribe faithfully):
- е (U+0435) dominant; є (U+0454) ~1/4 as common — see sweep rule above
- ѣ (U+0463 yat): вѣдали, нѣкоторыє, свѣдчу — ALWAYS write ѣ, never і or е
- и (U+0438) dominant; і (U+0456) ~1/4 as common — see sweep rule above
- я (U+044F): яко, християнамъ, пастыря — ALWAYS plain я, never ѧ
- ы (U+044B yeru): тыє, абы, были, оныхъ — different from и, check shape
- ъ (hard sign): христіанамъ, под — only where card shows it, NEVER add a trailing ъ
- ь (soft sign): where card shows it
- у (U+0443) dominant u-letter; ү (U+04AF) rare (~5% of cards, sporadic)
- ѳ (U+0473 fita): extremely rare on these cards (only in каѳолическое and similar Greek-origin words). Otherwise assume plain ф.

ALPHABET ABSENT — NEVER write these on Пересторога cards (they would modernize to Кройника-style orthography and are all false positives):
- ѫ, ѧ, ӕ, ї, ѹ, ω, ώ, Ѡ, ѯ, ѵ, s, ѕ
- combining double apostrophe ̾ (U+033E)
- combining acute ́ (U+0301)
- combining titlo ҃ (U+0483) — Пересторога has NO sacra nomina abbreviations
- паєрик (±), камора (†), придих („) — not used in this source

ABBREVIATIONS: Пересторога uses almost none. If you see a clear parenthesized expansion in the reference examples above ("(д)", "(т)", etc), treat it as archaic; otherwise transcribe the plain form. Six or fewer abbreviations exist in the entire 150-card corpus.

PUNCTUATION AND STRUCTURE:
- . , : — as written on the card
- … for lacunae
- ║ for page/column breaks in the source manuscript (rare)
- (?) for illegible or uncertain characters
- Section headers in mixed case or ALL CAPS as written
- Hyphenation: split words with a trailing hyphen on the line where they break, continue on the next line, exactly as the card shows

SOURCE REFERENCE LINE:
Pattern: "Львів, 1605-1606, Перест. {N}." — always at the bottom of the card. MUST be included as the last entry in "lines" AND parsed into the "source" object. Do not strip it.

---

CRITICAL REMINDERS:
- Default to plain letters (е, и, я, у) when the glyph is ambiguous. The card is EARLY UKRAINIAN, not Church Slavonic — archaic letters exist but are the minority.
- NEVER add a trailing ъ the card doesn't show (коронных not коронныхъ, под not подъ).
- NEVER substitute a familiar modern word for an unfamiliar archaic one.
- The banned-letter list above is MANDATORY. Writing any banned letter is a modernization error in the WRONG direction (over-archaicizing).
- When genuinely uncertain, write what you see and flag it in "notes".

Now transcribe the card in the image: $ARGUMENTS
