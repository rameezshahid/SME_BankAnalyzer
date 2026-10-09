from __future__ import annotations

import re
import unicodedata


ARABIC_PRESENTATION_RE = re.compile(r"[\ufb50-\ufdff\ufe70-\ufeff]")
ARABIC_SEGMENT_RE = re.compile(r"[\u0600-\u06ff]+(?:\s+[\u0600-\u06ff]+)*")

COMMON_ARABIC_PHRASES = {
    "ةبيرض": "ضريبة",
    "ةفاضملا ةميقلا": "القيمة المضافة",
    "ةميقلا ةفاضملا": "القيمة المضافة",
    "عيبلا طاقن": "نقاط البيع",
    "طاقن عيبلا": "نقاط البيع",
    "يعجرملا مقرلا": "الرقم المرجعي",
    "قاقحتسالا خيراتل": "لتاريخ الاستحقاق",
    "موسرل": "رسوم",
}


def _reverse_arabic_segment(match: re.Match) -> str:
    segment = match.group(0)
    words = segment.split()

    if not words:
        return segment

    reversed_words = [word[::-1] for word in words]

    if len(reversed_words) > 1:
        reversed_words = list(reversed(reversed_words))

    return " ".join(reversed_words)


def normalize_arabic_text(text: str | None) -> str:
    if not text:
        return ""

    has_presentation_forms = bool(ARABIC_PRESENTATION_RE.search(text))
    normalized = unicodedata.normalize("NFKC", text)

    for source, target in COMMON_ARABIC_PHRASES.items():
        normalized = normalized.replace(source, target)

    if has_presentation_forms:
        normalized = ARABIC_SEGMENT_RE.sub(_reverse_arabic_segment, normalized)

        for source, target in COMMON_ARABIC_PHRASES.items():
            normalized = normalized.replace(source, target)

    return " ".join(normalized.split())


def matching_text(text: str | None) -> str:
    normalized = normalize_arabic_text(text)
    if not text:
        return normalized

    # Keep the raw text too, because some bank-specific fragments are easier to
    # recognize before Arabic reordering. Pipe-separated so the last raw segment
    # doesn't merge with the first normalized one.
    return f"{text} | {normalized}"
