"""Object vocabulary shared by claim extraction, correction and CHAIR.

The 80 COCO classes and their synonyms come from the original CHAIR code
(Rohrbach et al., 2018; github.com/LisaAnne/Hallucination, data/synonyms.txt).
A few clothing words are added so attribute-binding demos (Table IV) work;
they are excluded from CHAIR because they are not COCO classes.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

SYNONYMS_PATH = Path(__file__).resolve().parents[1] / "data" / "coco_synonyms.txt"

COLORS = ("red", "blue", "green", "yellow", "black", "white", "orange", "brown", "gray", "purple", "pink")
COLOR_ALIASES = {"grey": "gray"}
MATERIALS = ("wooden", "metal", "plastic", "glass", "leather", "stone", "fabric", "paper")
MATERIAL_ALIASES = {"wood": "wooden", "metallic": "metal", "steel": "metal", "iron": "metal", "cloth": "fabric"}

# Non-COCO objects used for attribute-binding claims (clothing in Table IV).
EXTRA_OBJECTS = {
    "shirt": "shirt", "t-shirt": "shirt", "tshirt": "shirt", "blouse": "shirt", "jeans": "jeans",
    "pants": "pants", "trousers": "pants", "hat": "hat", "cap": "hat", "jacket": "jacket", "coat": "jacket",
    "dress": "dress", "shorts": "shorts", "skirt": "skirt", "sweater": "sweater", "hoodie": "sweater",
    "shoe": "shoe", "sneaker": "shoe", "boot": "shoe", "helmet": "helmet", "glasses": "glasses",
    "sunglasses": "glasses", "scarf": "scarf", "towel": "towel", "wall": "wall", "door": "door",
    "building": "building", "tree": "tree", "flower": "flower", "ball": "sports ball",
}

IRREGULAR = {"men": "man", "women": "woman", "children": "child", "mice": "mouse", "knives": "knife",
             "geese": "goose", "oxen": "ox", "teeth": "tooth", "feet": "foot", "people": "people",
             "policemen": "policeman", "gentlemen": "gentleman", "skis": "skis", "scissors": "scissors",
             "jeans": "jeans", "pants": "pants", "shorts": "shorts", "glasses": "glasses",
             "sunglasses": "sunglasses", "trousers": "trousers", "bus": "bus", "glass": "glass"}

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "a pair of": 2, "single": 1}
WORD_FOR_NUMBER = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
                   8: "eight", 9: "nine", 10: "ten"}


def _norm(phrase: str) -> str:
    return re.sub(r"\s+", " ", phrase.strip().lower())


@lru_cache(maxsize=1)
def _coco() -> tuple[list[str], dict[str, str]]:
    classes, synonyms = [], {}
    for line in SYNONYMS_PATH.read_text(encoding="utf-8").splitlines():
        words = [_norm(word) for word in line.split(",") if word.strip()]
        if not words: continue
        classes.append(words[0])
        for word in words:
            synonyms.setdefault(word, words[0])
    return classes, synonyms


def coco_classes() -> list[str]:
    return list(_coco()[0])


def _lookup(phrase: str, include_extra: bool) -> str | None:
    synonyms = _coco()[1]
    if phrase in synonyms: return synonyms[phrase]
    if include_extra and phrase in EXTRA_OBJECTS: return EXTRA_OBJECTS[phrase]
    return None


def singular_candidates(word: str) -> list[str]:
    """Possible singular forms of the last word, most specific first."""
    if word in IRREGULAR: return [IRREGULAR[word]]
    out = [word]
    if word.endswith("ies") and len(word) > 4: out.append(word[:-3] + "y")
    if word.endswith("ves"): out += [word[:-3] + "f", word[:-3] + "fe"]
    if word.endswith("es"): out.append(word[:-2])
    if word.endswith("s") and not word.endswith("ss"): out.append(word[:-1])
    return out


def to_class(phrase: str, include_extra: bool = True) -> str | None:
    """Map a surface phrase ("men", "motorbike", "dining tables") to its class."""
    phrase = _norm(phrase)
    if not phrase: return None
    *head, last = phrase.split(" ")
    for form in singular_candidates(last):
        found = _lookup(" ".join([*head, form]), include_extra)
        if found: return found
    return None


def surface_forms(cls: str) -> list[str]:
    """Every synonym of a class (plus plurals), longest first, for text edits."""
    forms = {word for word, target in _coco()[1].items() if target == cls}
    forms |= {word for word, target in EXTRA_OBJECTS.items() if target == cls}
    forms.add(cls)
    plurals = set()
    for form in forms:
        if form.endswith(("s", "x", "ch", "sh")): plurals.add(form + "es")
        elif form.endswith("y") and form[-2:-1] not in "aeiou": plurals.add(form[:-1] + "ies")
        else: plurals.add(form + "s")
    plurals |= {plural for plural, singular in IRREGULAR.items() if singular in forms}
    return sorted(forms | plurals, key=len, reverse=True)


_TOKEN = re.compile(r"[a-z]+(?:-[a-z]+)*")


def find_objects(text: str, include_extra: bool = False) -> list[tuple[str, int, int]]:
    """Object mentions as (class, start, end): longest phrase first, no overlaps.

    ``orange`` directly before another object/clothing word is read as a colour,
    not the fruit (the original CHAIR list would count it as a mention).
    """
    lower = text.lower()
    tokens = [(m.group(0), m.start(), m.end()) for m in _TOKEN.finditer(lower)]
    found, index = [], 0
    while index < len(tokens):
        match = None
        for size in (3, 2, 1):
            if index + size > len(tokens): continue
            phrase = " ".join(token for token, _, _ in tokens[index:index + size])
            cls = to_class(phrase, include_extra)
            if cls:
                match = (cls, tokens[index][1], tokens[index + size - 1][2], size); break
        if match:
            cls, start, end, size = match
            following = tokens[index + size][0] if index + size < len(tokens) else ""
            if size == 1 and tokens[index][0] in COLORS and following and to_class(following, True):
                index += 1; continue
            found.append((cls, start, end)); index += size
        else:
            index += 1
    return found
