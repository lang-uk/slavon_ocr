#!/usr/bin/env python3
"""Analyze character usage across OCR JSON transcriptions to identify uncommon characters for an editor toolbar."""

import json
import unicodedata
from collections import Counter
from pathlib import Path

FOLDER = Path("output/Auto-Color0002")

# Characters that are "normal" and don't need a toolbar button
COMMON = set(
    "абвгдежзийклмнопрстуфхцчшщъыьэюя"
    "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " .,;:!?-–—()[]{}\"'«»/\\|…\n\t"
    "іІїЇєЄґҐ"  # standard Ukrainian
)


def main():
    all_text = []
    n_files = 0

    for jf in sorted(FOLDER.glob("*.json")):
        try:
            data = json.loads(jf.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        lines = data.get("lines")
        if not lines:
            continue

        n_files += 1
        for line in lines:
            all_text.append(line)

    full = "\n".join(all_text)
    print(f"Analyzed {n_files} JSON files, {len(full)} total characters\n")

    # Count every character
    char_counts = Counter(full)

    # Separate base characters from combining marks
    base_chars = Counter()
    combining_marks = Counter()
    for ch, cnt in char_counts.items():
        cat = unicodedata.category(ch)
        if cat.startswith("M"):  # combining mark
            combining_marks[ch] = cnt
        else:
            base_chars[ch] = cnt

    # Uncommon base characters (not in COMMON set)
    uncommon_base = {ch: cnt for ch, cnt in base_chars.items() if ch not in COMMON}

    print("=" * 70)
    print("UNCOMMON BASE CHARACTERS (sorted by frequency)")
    print("=" * 70)
    print(f"{'Char':<6} {'U+':<8} {'Count':>6}  {'Name'}")
    print("-" * 70)
    for ch, cnt in sorted(uncommon_base.items(), key=lambda x: -x[1]):
        cp = f"U+{ord(ch):04X}"
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = "(unknown)"
        print(f"  {ch:<4}   {cp:<8} {cnt:>6}  {name}")

    print()
    print("=" * 70)
    print("COMBINING MARKS (sorted by frequency)")
    print("=" * 70)
    print(f"{'Mark':<6} {'U+':<8} {'Count':>6}  {'Name'}")
    print("-" * 70)
    for ch, cnt in sorted(combining_marks.items(), key=lambda x: -x[1]):
        cp = f"U+{ord(ch):04X}"
        try:
            name = unicodedata.name(ch)
        except ValueError:
            name = "(unknown)"
        # show combining mark on a dotted circle
        print(f"  \u25CC{ch:<3}   {cp:<8} {cnt:>6}  {name}")

    # Print a ready-to-use toolbar grouping
    print()
    print("=" * 70)
    print("SUGGESTED TOOLBAR GROUPS")
    print("=" * 70)

    groups = {
        "Archaic vowels": [],
        "Archaic consonants / special": [],
        "Greek-origin": [],
        "Combining diacritics": [],
        "Punctuation / structural": [],
    }

    archaic_vowels = "ѣѫѧӕѵѹүω"
    archaic_consonants = "ѳѯѕs"
    greek_origin = "ωώѠ"  # Ѡ uppercase

    for ch, cnt in sorted(uncommon_base.items(), key=lambda x: -x[1]):
        if ch.lower() in archaic_vowels or ch in archaic_vowels:
            groups["Archaic vowels"].append((ch, cnt))
        elif ch.lower() in archaic_consonants or ch in archaic_consonants:
            groups["Archaic consonants / special"].append((ch, cnt))
        elif ch in greek_origin:
            groups["Greek-origin"].append((ch, cnt))
        elif unicodedata.category(ch).startswith("P") or unicodedata.category(ch).startswith("S"):
            groups["Punctuation / structural"].append((ch, cnt))
        else:
            # Fallback: put remaining letters into archaic
            groups["Archaic consonants / special"].append((ch, cnt))

    for ch, cnt in sorted(combining_marks.items(), key=lambda x: -x[1]):
        groups["Combining diacritics"].append((ch, cnt))

    for group_name, chars in groups.items():
        if not chars:
            continue
        char_str = " ".join(f"{ch}" for ch, _ in chars)
        print(f"\n{group_name}:")
        for ch, cnt in chars:
            cp = f"U+{ord(ch):04X}"
            try:
                name = unicodedata.name(ch)
            except ValueError:
                name = "(unknown)"
            display = f"\u25CC{ch}" if unicodedata.category(ch).startswith("M") else ch
            print(f"  {display:<4}  {cp:<8} ({cnt:>4}x)  {name}")

    # Print compact toolbar string
    print()
    print("=" * 70)
    print("TOOLBAR STRING (copy-paste ready, ordered by group)")
    print("=" * 70)
    toolbar = []
    for group_name, chars in groups.items():
        if chars:
            toolbar.append(" ".join(ch for ch, _ in chars))
    print(" | ".join(toolbar))


if __name__ == "__main__":
    main()
