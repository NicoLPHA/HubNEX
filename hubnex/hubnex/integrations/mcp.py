"""A small MCP client (Model Context Protocol, "Streamable HTTP" transport).

Enough to connect the programs people use at work: initialize the session, list the tools
the server offers and call them. The server may answer a request with plain JSON or with
a short event stream (SSE); both are handled.
"""

from __future__ import annotations

import itertools
import json
from typing import Any

import httpx

from hubnex import __version__
from hubnex.i18n import tr

PROTOCOL_VERSION = "2025-06-18"


class MCPError(Exception):
    pass


class MCPClient:
    def __init__(self, url: str, headers: dict[str, str] | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.url = url
        self._client = httpx.AsyncClient(headers=headers or {}, timeout=httpx.Timeout(60, connect=15), transport=transport)
        self._ids = itertools.count(1)
        self._session: str | None = None
        self._ready = False

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ protocol
    async def _post(self, message: dict) -> httpx.Response:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        if self._ready:
            headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
        try:
            return await self._client.post(self.url, json=message, headers=headers)
        except httpx.HTTPError as exc:
            raise MCPError(tr("server non raggiungibile: {a}", a=exc)) from exc

    async def _request(self, method: str, params: dict | None = None) -> Any:
        mid = next(self._ids)
        r = await self._post({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})
        if r.status_code == 404 and self._session:  # the server forgot our session: start again
            self._session, self._ready = None, False
            raise _SessionExpired()
        if r.status_code in (401, 403):
            raise MCPError(tr("accesso negato ({a}): controlla il token del connettore", a=r.status_code))
        if r.status_code >= 400:
            raise MCPError(f"errore {r.status_code}: {r.text[:200]}")
        if sid := r.headers.get("mcp-session-id"):
            self._session = sid
        msg = self._find(r, mid)
        if "error" in msg:
            err = msg["error"]
            raise MCPError(err.get("message") or str(err))
        return msg.get("result")

    @staticmethod
    def _find(r: httpx.Response, mid: int) -> dict:
        if r.headers.get("content-type", "").startswith("text/event-stream"):
            for event in r.text.split("\n\n"):
                data = "\n".join(line[5:].strip() for line in event.splitlines() if line.startswith("data:"))
                if not data:
                    continue
                try:
                    msg = json.loads(data)
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == mid:
                    return msg
            raise MCPError(tr("risposta del server senza esito"))
        try:
            msg = r.json()
        except ValueError as exc:
            raise MCPError(tr("risposta del server non valida")) from exc
        if isinstance(msg, list):  # a batch: pick ours
            msg = next((m for m in msg if m.get("id") == mid), {})
        return msg

    async def _connect(self) -> None:
        if self._ready:
            return
        await self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "HubNEX", "version": __version__},
        })
        self._ready = True
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def call(self, method: str, params: dict | None = None) -> Any:
        for attempt in (1, 2):
            await self._connect()
            try:
                return await self._request(method, params)
            except _SessionExpired:
                if attempt == 2:
                    raise MCPError(tr("sessione scaduta"))
        return None

    # ------------------------------------------------------------------ tools
    async def list_tools(self) -> list[dict]:
        tools, cursor = [], None
        for _ in range(20):  # pages
            result = await self.call("tools/list", {"cursor": cursor} if cursor else {}) or {}
            tools.extend(result.get("tools", []))
            cursor = result.get("nextCursor")
            if not cursor:
                break
        return tools

    async def call_tool(self, name: str, arguments: dict) -> tuple[str, bool]:
        """The tool's answer as text, and whether the server says it failed."""
        result = await self.call("tools/call", {"name": name, "arguments": arguments}) or {}
        parts = []
        for c in result.get("content", []):
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif c.get("type") == "resource" and isinstance(c.get("resource"), dict):
                parts.append(c["resource"].get("text", ""))
            else:
                parts.append(f"[{c.get('type')}]")
        if not any(parts) and result.get("structuredContent") is not None:
            parts.append(json.dumps(result["structuredContent"], ensure_ascii=False))
        return "\n".join(p for p in parts if p) or "(nessun contenuto)", bool(result.get("isError"))


class _SessionExpired(Exception):
    pass
