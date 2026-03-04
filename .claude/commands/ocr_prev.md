Transcribe the handwritten research card in the provided image.

These are 20th-century scholar's index cards copying excerpts from early 17th-century Ukrainian (Ruthenian) sources — primarily the Lviv chronicle ("Кройника") but also panegyric verse, polemical texts, and other period documents. The orthography ranges from deep archaic Church Slavonic to relatively modern early Ukrainian depending on the source.

---

STEP 1 — PREPROCESSING CHECKS (do these FIRST):

1. EXISTING OUTPUT: Check if a .json file with the same name already exists next to the image. If it does, SKIP and report "already transcribed". Only re-transcribe if explicitly told to overwrite (e.g. /ocr --force @path/to/image.jpg).

2. BLANK CARDS: If the card is blank or contains only smudges/artifacts, output the error JSON with error_type "blank".

---

STEP 2 — TRANSCRIBE:

Read each letter INDIVIDUALLY, character by character. Archaic words will look unfamiliar — that is expected. Do NOT guess words by overall shape or substitute a more familiar word for what is actually written.

Preserve the line structure of the card exactly: each handwritten line becomes one entry in the "lines" array, for ALL card types (prose, verse, everything). This allows alignment between image lines and transcribed lines.

---

STEP 3 — VERIFY BEFORE SAVING:

Re-read the image and compare against your transcription line by line. Specifically check for these common errors:
- INSERTED LETTERS: characters added that are not on the card (e.g. writing коронныхъ when card shows коронных — the trailing ъ is not there)
- SUBSTITUTED WORDS: a familiar word replacing an unfamiliar one (e.g. writing сүнодъ when card actually shows сыномъ)
- є/е CONFUSION: writing є where the card shows е, or vice versa (e.g. writing єпископовє when card shows епископове). Check EVERY instance of е/є against the card.
- MODERNIZED SPELLING: archaic letters silently replaced with modern equivalents
- MISSING CHARACTERS: letters on the card that were skipped in transcription

If you find errors, fix them before saving. When genuinely uncertain about a character, put your best reading and note the uncertainty in "notes".

---

STEP 4 — SAVE OUTPUT:

Save a JSON file next to the source image, same filename but .json extension.
Example: @data/cards/Scan0042.jpg → data/cards/Scan0042.json

---

JSON SCHEMA:

For successfully transcribed cards (all types):
```json
{
  "filename": "Scan0042.jpg",
  "card_numbers": {
    "primary": "18",
    "secondary": null,
    "tertiary": null,
    "notes": "18 top-left ink"
  },
  "lines": [
    "ω(т)толѣ вѣримо в̾ши(т)ко доброє поимовáти",
    "ω(т) нєго, порүчáючи єму кождүю рє(ч҃) в̾",
    "єго мо(ц҃). нє довѣдүючисѧ…"
  ],
  "source": {
    "city": "Львів",
    "date": "поч. ХѴІІ ст.",
    "reference": "Крон. 3 зв."
  },
  "notes": ""
}
```

For cards with multiple numbers:
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
    "томные часы православнымъ христіанамъ,",
    "святое каѳолическое восточное церкве",
    "сыномъ, абы вѣдали, яко нѣкоторые епи-",
    "скопове панствъ коронных, которые непер-",
    "ва подъ владзою и подъ послушенствомъ",
    "святѣйшаго вселенскаго константино-",
    "полскаго патріархи были"
  ],
  "source": {
    "city": "Львів",
    "date": "1605-1606",
    "reference": "Берест. 25."
  },
  "notes": ""
}
```

For errors (blank, illegible):
```json
{
  "filename": "Scan0077.jpg",
  "card_numbers": {
    "primary": null,
    "secondary": null,
    "tertiary": null,
    "notes": ""
  },
  "lines": null,
  "source": null,
  "notes": "Description of the problem",
  "error_type": "blank | illegible"
}
```

---

CARD NUMBERS: Cards may have MULTIPLE numbers in different positions, hands, or inks. Capture ALL visible numbers:
- "primary": the scholar's sequence number (often top-left, smaller, sometimes pencil)
- "secondary": catalog/inventory number if present (often top-center or top-right, sometimes different ink or larger)
- "tertiary": any additional number (bottom corner, stamped, marginal)
- "notes": position and appearance of each (e.g. "22 top-left pencil, 221 top-center ink, 1 bottom-right corner")
Set unused fields to null.

---

ENCODING RULES:

ABBREVIATIONS AND EXPANSIONS
- Letters expanded from titla abbreviations or superscript letters go in PARENTHESES: ω(т)толѣ, в̾ши(т)ко, є(д)но, почина(л҃), котόро(г҃)
- Titlo mark U+0483 (◌҃) goes INSIDE parentheses for abbreviated letters: (л҃), (ч҃), (ц҃), (н҃), (т҃), (с҃), (д҃), (г҃), (ж҃), (ш҃), (в҃), (м҃), (и҃), (р҃), (к҃), (а҃)
- Titlo on sacra nomina stays OUTSIDE parentheses directly on the base letter: г҃ъ, бг҃ь, нб҃о, слн҃цє(м), дн҃и, сн҃ъ, гд҃ь, дх҃а, ст҃ы(и), бж҃їє, чл҃къ, ц҃ръ, хс҃/х҃с, іс҃, мл҃тва, гл҃є(т҃), сщ҃єн̾ни(к҃), бл(с҃)вєн̾ство, хр(с҃)тїа(н҃)скїй, єѵ(г҃)лїи, ап(с҃)лω(м), пр(о҃)рка, рж(с҃)твѣ, м(с҃)ца, см҃рти
- Cyrillic numeral titlo: а҃, в҃, г҃, є҃, о҃, р҃, м҃, п҃, т҃, ц҃
- Some cards (polemical texts, later sources) use fewer abbreviations or more modern orthography. Transcribe what is on the card — do not add archaic features the card does not show.

DIACRITICS
- Combining double apostrophe above U+033E (◌̾) for the reduced yer/superscript ъ tick: в̾ши(т)ко, хробáц̾ство, драпѣж̾ныи, з̾, л̾вєи, мѣст̾ца, инак̾
- Combining acute U+0301 (◌́) on stressed vowels ONLY where marked on the card. Do NOT add accents the card does not show.
- Combining tilde U+0303 (◌̃) if visible over a letter — reproduce as written.

ALPHABET — ARCHAIC CHARACTERS (never modernize)
- ω (U+03C9 Greek small omega). When card shows ot-ligature: ω(т). Plain: ω змїю, ωколо
- ώ (U+03CE omega with tonos) for stressed omega: ώнъ, ώкрүтъ
- Ѡ (U+0460 Cyrillic round omega) for section headers: Ѡ трє(х) сн҃охъ
- ѣ (U+0463 yat): вѣримо, звѣри, свѣтлостѧ(ми)
- ѫ (U+046B big yus): тѫ, зόвѫ(т҃), сѫ(т҃), бѫ(дє)тъ, часѫ
- ѧ (U+0467 little yus): сѧ, чєлѧ(д)ный, мовѧчи, ѧзыко(м)
- ӕ (U+04D5 iotified a): ӕко, ӕвлєнїє
- ѯ (U+0471 ksi): финиѯѣ, алєѯа(н҃)дръ
- ѳ (U+0473 fita): сиѳъ, арѳаѯаса(т҃), каѳолическое
- ѵ (U+0475 izhitsa): мώѵсєωвыхъ, вавѵ(и)лонъ, єѵ(г҃)лїи
- s (Latin s) for zelo: sвѣsдами, sмїю, sлѣ — distinct from з and ѕ
- ѕ (U+0455 dze): ѕлόстїй, ѕвѣрѧ(т҃), ѕлόго, дрүѕїй — distinct from з and s
- ъ (hard sign): ώнъ, ω(т)ц҃ъ, въ, прєдъ
- ы (yeru): ѣдовитыи, драпѣж̾ныи, быти

VOWEL LETTERS
- є (U+0454) and е (U+0435) are BOTH valid. Do NOT default to either one. Кройника cards predominantly use є: єму, єго, нє. Other sources (polemical texts, later documents) may use plain е: епископове, веленскаго. Transcribe EXACTLY what the card shows. Look at each instance individually. Writing є where the card shows е is a frequent error.
- ї (U+0457) for iotified i with two dots: змїю, үчєнїи, дїавόло(м)
- ү (U+04AF straight u) as dominant u-letter in Кройника: порүчáючи, кождүю, мүхи. Other sources may use plain у. Transcribe what is on the card.
- ѹ (U+0479 uk digraph) where card shows digraph form: почáткѹ, василискѹ, жєнѹ, дорогѹ

BRACKETS AND SPECIAL CHARACTERS
- ( ) for editorial expansions of abbreviations as described above.
- If the scholar uses angle-bracket-like marks, use ‹ › (U+2039/U+203A) or « » (U+00AB/U+00BB), NOT < > which break JSON.
- Never use raw < or > inside JSON string values.

PUNCTUATION AND STRUCTURE
- . for sentence boundaries
- … for omissions/lacunae
- ║ for page/column breaks in the source manuscript
- : and , as written
- (?) for illegible or uncertain characters
- Section headers in mixed case or ALL CAPS: РОЗДѣЛъ, ВѢКъ, Ѡ ЖИДОХ̾
- Hyphenation: if a word is split across lines with a hyphen, keep the hyphen at the end of the line and continue the word on the next line, exactly as the card shows.

SOURCE REFERENCE FORMAT:
Transcribe the reference line exactly as written on the card. Common patterns:
- Chronicle: Львів, поч. ХѴІІ ст. Крон. {N} зв.
- Verse: Київ, 1622, Сак. Вірші, МҮКСВ 40.
- Polemical: Львів, 1605-1606, Берест. 25.
Use Cyrillic lookalikes in Roman numerals where the card does: Х, Ѵ, І (not Latin X, V, I).

CRITICAL REMINDERS:
- NEVER modernize: do not replace ѣ→і, ѫ→у, ω→о, є→е, ї→і, ъ→(nothing), ѕ→з, s→з
- NEVER ADD characters that are not on the card. If a word ends without ъ, do not add ъ.
- NEVER SUBSTITUTE a familiar word for an unfamiliar one. If the card says сыномъ, do not write сүнодъ.
- є and е are DIFFERENT LETTERS. Check every instance against the card.
- ү and у are DIFFERENT LETTERS. Check every instance against the card.
- When uncertain, write what you see and flag it in "notes". Do not silently pick the more familiar reading.
- Cards from different sources have different orthographic conventions — transcribe exactly what is written on each card.

Now transcribe the card(s) in the image: $ARGUMENTS