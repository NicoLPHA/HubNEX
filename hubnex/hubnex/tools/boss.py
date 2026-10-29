"""Jarvis-only tools: managing the team."""

from __future__ import annotations

from hubnex.context import CURRENT_CHAT
from hubnex.tools import ToolContext, tool


@tool(
    "team_overview",
    "Mostra aziende, reparti e agenti del team con il loro stato attuale.",
    {},
)
async def team_overview(ctx: ToolContext, inp: dict):
    return ctx.hq.team_snapshot()


@tool(
    "delegate",
    "Assegna un compito a un agente del team. Con wait=true aspetti il risultato e lo usi nella "
    "risposta (per lavori brevi). Con wait=false l'agente lavora in background e il risultato "
    "arriva all'utente su Telegram/dashboard quando ha finito (per lavori lunghi). Scrivi il "
    "compito in modo completo: l'agente non vede la tua conversazione.",
    {
        "agent_id": {"type": "string"},
        "task": {"type": "string"},
        "wait": {"type": "boolean"},
    },
    ["agent_id", "task"],
)
async def delegate(ctx: ToolContext, inp: dict):
    agent_id = inp["agent_id"]
    if agent_id not in ctx.hq.agents:
        return {"errore": f"Agente sconosciuto '{agent_id}'. Usa team_overview."}
    if inp.get("wait", True):
        result = await ctx.hq.run_agent(agent_id, inp["task"], source=ctx.agent_id)
        chat = CURRENT_CHAT.get()
        if chat and ctx.hq.team_enabled:
            # In the Telegram group the agent answers with its own voice (and bot).
            await ctx.hq.team.post(agent_id, result, chat)
            return {"agente": agent_id, "risultato": result, "gia_mostrato_all_utente": True}
        return {"agente": agent_id, "risultato": result}
    ctx.hq.run_agent_background(agent_id, inp["task"], source=ctx.agent_id, report=True)
    return {"agente": agent_id, "stato": "avviato in background"}


@tool(
    "agent_history",
    "Ultimi compiti svolti da un agente, con i risultati.",
    {"agent_id": {"type": "string"}},
    ["agent_id"],
)
async def agent_history(ctx: ToolContext, inp: dict):
    rows = await ctx.hq.store.agent_tasks(inp["agent_id"], 5)
    return [
        {"compito": r["task"], "stato": r["status"], "risultato": (r["result"] or "")[:1500]} for r in rows
    ] or "Nessun compito."


@tool(
    "owner_rules",
    "Regole permanenti dell'utente, valide per te e per tutti gli agenti (sono nelle istruzioni di "
    "ognuno). action=add per salvare un'istruzione generale che l'utente ti dà (\"non fare mai…\", "
    "\"d'ora in poi…\"), scritta in modo chiaro e completo; action=remove con il numero per "
    "toglierla quando l'utente lo chiede; action=list per vederle.",
    {
        "action": {"type": "string", "enum": ["add", "remove", "list"]},
        "rule": {"type": "string"},
        "number": {"type": "integer"},
    },
    ["action"],
)
async def owner_rules(ctx: ToolContext, inp: dict):
    hq = ctx.hq
    if inp["action"] == "add" and inp.get("rule", "").strip():
        hq.rules.append(inp["rule"].strip())
        await hq.log("memory", f"Nuova regola: {inp['rule'].strip()}", ctx.agent_id)
    elif inp["action"] == "remove":
        n = inp.get("number") or 0
        if not 1 <= n <= len(hq.rules):
            return {"errore": f"Regola {n} inesistente.", "regole": hq.rules}
        removed = hq.rules.pop(n - 1)
        await hq.log("memory", f"Regola tolta: {removed}", ctx.agent_id)
    await hq.store.put("owner_rules", hq.rules)
    return {"regole": {i: r for i, r in enumerate(hq.rules, 1)} or "Nessuna regola."}
