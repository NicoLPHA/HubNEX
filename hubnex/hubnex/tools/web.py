"""web_fetch for models other than Claude (Claude has Anthropic's own, run on their servers).

Only public addresses: an agent reading a page must never reach into the home network.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from hubnex.tools import ToolContext, tool

MAX_BYTES = 2_000_000
MAX_CHARS = 20_000


class _Text(HTMLParser):
    """The readable text of a page: no scripts, styles or markup."""

    SKIP = {"script", "style", "noscript", "svg", "head", "template"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "header", "footer"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if not self.skip:
            self.out.append(data)


def html_to_text(html: str) -> tuple[str, str]:
    p = _Text()
    p.feed(html)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.out))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return p.title.strip(), text


async def public_host(host: str) -> bool:
    """True if every address of `host` is public (not the house, not the add-on itself)."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return False
    addrs = {ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos}
    return bool(addrs) and all(a.is_global for a in addrs)


async def fetch(url: str, client: httpx.AsyncClient | None = None) -> dict:
    own = client is None
    client = client or httpx.AsyncClient(timeout=20, headers={"User-Agent": "HubNEX/1.0 (+https://github.com/P1pp89/HubNEX)"})
    try:
        for _ in range(5):  # redirects by hand: each hop is checked
            u = urlparse(url)
            if u.scheme not in ("http", "https") or not u.hostname:
                return {"errore": "Solo indirizzi http o https."}
            if not await public_host(u.hostname):
                return {"errore": "Indirizzo non pubblico: non lo apro."}
            async with client.stream("GET", url) as r:
                if r.is_redirect and r.headers.get("location"):
                    url = urljoin(url, r.headers["location"])
                    continue
                if r.status_code >= 400:
                    return {"errore": f"La pagina risponde {r.status_code}."}
                body = b""
                async for chunk in r.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        break
                ctype = r.headers.get("content-type", "")
                charset = r.charset_encoding or "utf-8"
            raw = body.decode(charset, errors="replace")
            if "html" in ctype or raw.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
                title, text = html_to_text(raw)
            elif ctype.startswith("text/") or "json" in ctype or "xml" in ctype:
                title, text = "", raw
            else:
                return {"errore": f"Contenuto non testuale ({ctype or 'sconosciuto'})."}
            out = {"url": url, "titolo": title, "testo": text[:MAX_CHARS]}
            if len(text) > MAX_CHARS:
                out["troncato"] = True
            return out
        return {"errore": "Troppi reindirizzamenti."}
    except httpx.HTTPError as exc:
        return {"errore": f"Pagina non raggiungibile: {exc}"}
    finally:
        if own:
            await client.aclose()


@tool(
    "web_fetch",
    "Legge una pagina web pubblica dal suo indirizzo e ne restituisce il testo.",
    {"url": {"type": "string", "description": "L'indirizzo completo, con https://"}},
    ["url"],
)
async def web_fetch(ctx: ToolContext, inp: dict):
    return await fetch(inp["url"])
