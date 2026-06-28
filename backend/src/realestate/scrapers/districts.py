from __future__ import annotations

import re
from difflib import SequenceMatcher

from realestate.locations import DISTRICT_BY_KEY, location_key

_FUZZY_THRESHOLD = 0.86


def district_from_investment(value: str | None) -> str | None:
    return district_from_text(value)


def district_from_text(value: str | None) -> str | None:
    key = location_key(value)
    if not key:
        return None
    matches = []
    for district_key, district in DISTRICT_BY_KEY.items():
        district_words = district_key.split()
        if not district_words:
            continue
        if district_key == key or _contains_word_sequence(key, district_key):
            matches.append((len(district_words), district.name))
            continue
        if len(district_words) == 1 and _contains_word_sequence(key, district_key):
            matches.append((1, district.name))
    if not matches:
        return _fuzzy_district_from_key(key)
    matches.sort(reverse=True)
    return matches[0][1]


def _contains_word_sequence(text_key: str, needle_key: str) -> bool:
    return re.search(rf"(?:^|\s){re.escape(needle_key)}(?:\s|$)", text_key) is not None


def _fuzzy_district_from_key(text_key: str) -> str | None:
    text_words = text_key.split()
    if not text_words:
        return None
    best: tuple[float, int, str] | None = None
    for district_key, district in DISTRICT_BY_KEY.items():
        district_words = district_key.split()
        if not district_words:
            continue
        candidates = _candidate_phrases(text_words, len(district_words))
        for candidate in candidates:
            score = SequenceMatcher(None, candidate, district_key).ratio()
            if score < _FUZZY_THRESHOLD:
                continue
            current = (score, len(district_words), district.name)
            if best is None or current > best:
                best = current
    return best[2] if best else None


def _candidate_phrases(words: list[str], size: int) -> list[str]:
    if size <= 0 or len(words) < size:
        return []
    return [" ".join(words[index : index + size]) for index in range(len(words) - size + 1)]
