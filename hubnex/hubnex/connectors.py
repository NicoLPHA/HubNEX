"""Connectors: the programs of your work (management software, calendar, CRM…) through MCP.

Each connector in agents.yaml is an MCP server. Its tools are offered to the agents listed
for it, named "<connector>__<tool>". Tools that only read run freely; tools that change data
become a pending action that runs only after the owner's ✅ (see actions.py).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from hubnex.config import ConnectorSpec
from hubnex.integrations.mcp import MCPClient, MCPError

if TYPE_CHECKING:
    from hubnex.hq import HQ

log = logging.getLogger("hubnex.connectors")
REFRESH_SECONDS = 15 * 60
MAX_RESULT = 15_000
# Without annotations from the server, these names are taken as read-only.
READ_PREFIXES = ("get", "list", "search", "read", "find", "query", "fetch", "count", "describe", "lookup", "show", "cerca", "leggi", "elenca")


@dataclass
class ConnectorTool:
    connector: str
    name: str  # as the server calls it
    title: str
    description: str
    schema: dict
    confirm: bool

    @property
    def full_name(self) -> str:
        return tool_name(self.connector, self.name)


@dataclass
class Connector:
    spec: ConnectorSpec
    client: MCPClient
    tools: dict[str, ConnectorTool] = field(default_factory=dict)  # by full name
    loaded: float = 0.0
    error: str | None = None


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "mcp"


def tool_name(connector: str, tool: str) -> str:
    return f"{slug(connector)}__{re.sub(r'[^A-Za-z0-9_-]', '_', tool)}"[:64]


def needs_confirmation(spec: ConnectorSpec, tool: dict) -> bool:
    name = tool.get("name", "")
    if spec.confirm == "never" or name in spec.free:
        return False
    if spec.confirm == "always" or name in spec.always_confirm:
        return True
    hints = tool.get("annotations") or {}
    if hints.get("readOnlyHint") is True:
        return False
    if hints.get("readOnlyHint") is False or hints.get("destructiveHint") is True:
        return True
    return not name.lower().startswith(READ_PREFIXES)


def summarize(tool: ConnectorTool, args: dict) -> str:
    lines = [f"{tool.connector}: {tool.title}"]
    for k, v in args.items():
        value = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        lines.append(f"• {k}: {value[:300]}")
    return "\n".join(lines)


class Connectors:
    def __init__(self, hq: "HQ", specs: list[ConnectorSpec], transport=None):
        self.hq = hq
        self.items = {
            slug(s.name): Connector(s, MCPClient(s.url, s.headers(), transport=transport)) for s in specs
        }
        hq.actions.executors["mcp"] = self._run_confirmed

    @property
    def enabled(self) -> bool:
        return bool(self.items)

    async def close(self) -> None:
        for c in self.items.values():
            await c.client.close()

    async def _load(self, c: Connector) -> None:
        if c.loaded and time.monotonic() - c.loaded < REFRESH_SECONDS:
            return
        try:
            raw = await c.client.list_tools()
        except MCPError as exc:
            if c.error != str(exc):
                await self.hq.log("error", f"Connettore {c.spec.name}: {exc}")
            c.error, c.loaded = str(exc), time.monotonic() - REFRESH_SECONDS + 60  # retry in a minute
            return
        c.tools = {}
        for t in raw:
            if not t.get("name"):
                continue
            ct = ConnectorTool(
                connector=c.spec.name,
                name=t["name"],
                title=t.get("title") or (t.get("annotations") or {}).get("title") or t["name"],
                description=(t.get("description") or "").strip(),
                schema=t.get("inputSchema") or {"type": "object", "properties": {}},
                confirm=needs_confirmation(c.spec, t),
            )
            c.tools[ct.full_name] = ct
        c.error, c.loaded = None, time.monotonic()

    async def tools_for(self, agent_id: str) -> dict[str, ConnectorTool]:
        out: dict[str, ConnectorTool] = {}
        for c in self.items.values():
            if not c.spec.allows(agent_id):
                continue
            await self._load(c)
            out.update(c.tools)
        return out

    @staticmethod
    def definition(t: ConnectorTool) -> dict:
        desc = f"[{t.connector}] {t.description}".strip()
        if t.confirm:
            desc += " (Modifica i dati: viene mostrata al proprietario e parte solo dopo la sua conferma.)"
        return {"name": t.full_name, "description": desc[:1024], "input_schema": t.schema}

    async def execute(self, t: ConnectorTool, args: dict, agent_id: str | None) -> tuple[str, bool]:
        if t.confirm:
            payload = {"connector": slug(t.connector), "tool": t.name, "args": args}
            return await self.hq.actions.propose("mcp", agent_id, summarize(t, args), payload, t.connector), False
        c = self.items[slug(t.connector)]
        try:
            text, failed = await c.client.call_tool(t.name, args)
        except MCPError as exc:
            return f"{t.connector}: {exc}", True
        return text[:MAX_RESULT], failed

    async def _run_confirmed(self, payload: dict) -> str:
        c = self.items.get(payload["connector"])
        if c is None:
            raise RuntimeError("connettore non più configurato")
        text, failed = await c.client.call_tool(payload["tool"], payload["args"])
        if failed:
            raise RuntimeError(text[:300])
        first = text.strip().splitlines()[0][:200] if text.strip() else ""
        return f"✅ fatto{': ' + first if first else ''}"

    async def status(self) -> list[str]:
        lines = []
        for c in self.items.values():
            c.loaded = 0.0  # /stato forces a fresh check
            await self._load(c)
            lines.append(f"{c.spec.name}: " + (f"⚠ {c.error}" if c.error else f"OK, {len(c.tools)} strumenti"))
        return lines

    def describe(self) -> list[dict[str, Any]]:
        return [{"name": c.spec.name, "tools": len(c.tools), "error": c.error} for c in self.items.values()]
