"""The Italian texts of the dashboard that need an English version: every t("…") in web/*.js and
the data-i18n texts and attributes of web/index.html.  python dev/i18n_keys.py [--missing]"""

import json
import re
import sys
from html import unescape
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
CALL = re.compile(r'\bt\(\s*"((?:[^"\\]|\\.)*)"')


def js_keys() -> set[str]:
    keys = set()
    for f in WEB.glob("*.js"):
        if f.name.startswith("i18n"):
            continue
        for m in CALL.finditer(f.read_text(encoding="utf-8")):
            keys.add(json.loads(f'"{m.group(1)}"'))
    return keys


def html_keys() -> set[str]:
    src = (WEB / "index.html").read_text(encoding="utf-8")
    keys = set()
    for m in re.finditer(r"<(\w+)([^>]*\bdata-i18n\b[^>]*)>([^<]*)", src):
        if "data-i18n-attr" in m.group(2) and not re.search(r"\bdata-i18n(?!-)", m.group(2)):
            continue
        text = unescape(m.group(3)).strip()
        if text:
            keys.add(text)
    for m in re.finditer(r'<\w+([^>]*\bdata-i18n-attr="([^"]+)"[^>]*)>', src):
        for attr in m.group(2).split(","):
            v = re.search(rf'\b{attr}="([^"]*)"', m.group(1))
            if v and v.group(1).strip():
                keys.add(unescape(v.group(1)))
    return keys


def english() -> dict:
    src = (WEB / "i18n-en.js").read_text(encoding="utf-8")
    body = src[src.index("{"): src.rindex("}") + 1]
    return json.loads(body)


if __name__ == "__main__":
    keys = js_keys() | html_keys()
    if "--missing" in sys.argv:
        have = english()
        keys = keys - set(have)
    print(json.dumps(sorted(keys), ensure_ascii=False, indent=0))
