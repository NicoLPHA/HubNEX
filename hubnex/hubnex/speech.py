"""Text made for the ear: what the voice reads instead of the written answer's symbols."""

from __future__ import annotations

import re

# Units after a number: "0,2 Ω" -> "0,2 ohm". Longest first, so "kWh" wins over "kW".
_UNITS = [
    ("kWh", "chilowattora"), ("MWh", "megawattora"), ("Wh", "wattora"),
    ("MΩ", "megaohm"), ("kΩ", "chiloohm"), ("mΩ", "milliohm"), ("Ω", "ohm"),
    ("kVA", "chilovoltampere"), ("kVAr", "chilovoltampere reattivi"), ("VA", "voltampere"),
    ("kW", "chilowatt"), ("MW", "megawatt"), ("W", "watt"),
    ("kV", "chilovolt"), ("mV", "millivolt"), ("V", "volt"),
    ("kA", "chiloampere"), ("mA", "milliampere"), ("A", "ampere"),
    ("°C", "gradi"), ("°", "gradi"), ("Hz", "hertz"),
    ("mm²", "millimetri quadrati"), ("mm2", "millimetri quadrati"), ("m²", "metri quadrati"),
    ("km", "chilometri"), ("cm", "centimetri"), ("mm", "millimetri"),
    ("ms", "millisecondi"), ("min", "minuti"), ("h", "ore"),
    ("%", "per cento"),
]
_UNIT_RE = re.compile(
    r"(?<=\d)\s?(" + "|".join(re.escape(u) for u, _ in sorted(_UNITS, key=lambda x: -len(x[0]))) + r")(?![\wΩ²])"
)
_UNIT_WORD = dict(_UNITS)

# Abbreviations read as words (whole words only).
_WORDS = {
    "MT/BT": "media e bassa tensione", "BT/MT": "bassa e media tensione",
    "MT": "media tensione", "BT": "bassa tensione", "AT": "alta tensione",
    "e/o": "e o", "ecc.": "eccetera", "es.": "per esempio", "p.es.": "per esempio",
    "N.B.": "nota bene", "tel.": "telefono", "n.": "numero",
}
_WORD_RE = re.compile(r"(?<![\w/])(" + "|".join(re.escape(w) for w in sorted(_WORDS, key=len, reverse=True)) + r")(?![\w/])")

_SYMBOLS = {
    "→": ", ", "⇒": ", ", "←": ", ", "·": ", ", "•": ", ", "|": ", ", "≈": " circa ",
    "≥": " maggiore o uguale a ", "≤": " minore o uguale a ", ">=": " maggiore o uguale a ",
    "<=": " minore o uguale a ", "±": " più o meno ", "×": " per ", "€": " euro ", "&": " e ",
    "~": " circa ", "§": " paragrafo ", "/": " ", "\\": " ", "=": " uguale ",
}
_MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
           "settembre", "ottobre", "novembre", "dicembre"]


def _date(m: re.Match) -> str:
    day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return m.group(0)
    return f"{day} {_MONTHS[month - 1]}" + (f" {year}" if year else "")


_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\u2300-\u23FF\u2B00-\u2BFF\uFE0F\u200D]"
)


def for_voice(text: str, limit: int = 2500) -> str:
    """The written answer as the voice should read it: no markdown, emoji, links or symbols,
    units and abbreviations as words, list items as sentences (a pause instead of a dash)."""
    if not text:
        return ""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)  # code blocks are not read
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)  # [label](url) -> label
    t = re.sub(r"https?://\S+|www\.\S+", "", t)
    t = _EMOJI.sub("", t)
    lines = []
    for line in t.splitlines():
        line = re.sub(r"^\s*(?:[-*+•·▪►]|\d+[.)])\s+", "", line)  # bullets and numbering
        line = re.sub(r"^\s*#+\s*", "", line)  # headings
        line = re.sub(r"[*_`>#]", "", line).strip()
        if not line:
            continue
        if line[-1] not in ".!?:;,":
            line += "."  # each line its own sentence: the voice pauses
        lines.append(line)
    t = " ".join(lines)
    t = _WORD_RE.sub(lambda m: _WORDS[m.group(1)], t)
    t = _UNIT_RE.sub(lambda m: " " + _UNIT_WORD[m.group(1)], t)
    t = re.sub(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", _date, t)  # 1/9/2021 -> 1 settembre 2021
    t = re.sub(r"(\d)/(\d)", r"\1 su \2", t)  # 1/300 -> 1 su 300
    t = re.sub(r"(\d)-(\d)", r"\1 \2", t)  # CEI 64-8 -> 64 8, not "64 meno 8"
    for sym, word in _SYMBOLS.items():
        t = t.replace(sym, word)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"([,.;:])[,.;:]+", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    if len(t) > limit:  # cut at the end of a sentence
        cut = t[:limit]
        t = cut[: max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! ")) + 1] or cut
    return t
