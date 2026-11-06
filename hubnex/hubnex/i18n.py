"""The add-on's languages: Italian, English or Dutch. The Italian text is the key ("gettext style"):
tr("bozza sconosciuta") is the Italian text itself, or its English/Dutch from i18n_en.EN / i18n_nl.NL.
Placeholders: tr("{n} stanze", n=3).

The language is the add-on's (option "language", else Home Assistant's own) for what the
add-on says by itself (activity feed, Telegram, notifications); a dashboard request carries
the viewer's language (X-HubNEX-Lang), which then wins for the answer to that request.
"""

from __future__ import annotations

from contextvars import ContextVar

from hubnex.i18n_en import EN
from hubnex.i18n_nl import NL

LANGS = ("it", "en", "nl")
DICTS = {"en": EN, "nl": NL}
_system = "it"
REQUEST_LANG: ContextVar[str | None] = ContextVar("request_lang", default=None)


def norm(lang: str | None) -> str | None:
    """'it-IT' -> 'it', 'nl-NL' -> 'nl'; anything else -> 'en'; empty -> None."""
    if not lang:
        return None
    code = str(lang).lower()
    return "it" if code.startswith("it") else "nl" if code.startswith("nl") else "en"


def set_system_lang(lang: str | None) -> None:
    global _system
    _system = norm(lang) or _system


def system_lang() -> str:
    return _system


def lang() -> str:
    return REQUEST_LANG.get() or _system


def _translate(text: str, language: str) -> str:
    if language == "it":
        return text
    return DICTS.get(language, EN).get(text, text)


def tr(text: str, **values) -> str:
    out = _translate(text, lang())
    return out.format(**values) if values else out


def tr_sys(text: str, **values) -> str:
    """In the add-on's own language, whatever request is being served (feed, Telegram…)."""
    out = _translate(text, _system)
    return out.format(**values) if values else out
