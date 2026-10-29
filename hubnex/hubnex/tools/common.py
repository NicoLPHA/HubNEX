"""Tools shared by every agent: memory, deadlines, notifications."""

from __future__ import annotations

from datetime import datetime

from hubnex.tools import ToolContext, tool


@tool(
    "memory_save",
    "Salva un'informazione utile da ricordare in futuro (preferenze, contatti, decisioni, dati "
    "aziendali). Scope 'global' = valida ovunque, altrimenti resta legata alla tua azienda.",
    {
        "topic": {"type": "string", "description": "Titolo breve"},
        "content": {"type": "string"},
        "global": {"type": "boolean", "description": "true per renderla visibile a tutte le aziende"},
    },
    ["topic", "content"],
)
async def memory_save(ctx: ToolContext, inp: dict):
    scope = "global" if inp.get("global") or not ctx.company else ctx.company
    mid = await ctx.hq.store.remember(scope, inp["topic"], inp["content"], ctx.agent_id)
    await ctx.hq.log("memory", f"Ricordo: {inp['topic']}", ctx.agent_id)
    await ctx.hq.emit_stats()
    return {"ok": True, "id": mid}


@tool(
    "memory_search",
    "Cerca nella memoria condivisa (note salvate da te, da Jarvis o dagli altri agenti).",
    {"query": {"type": "string", "description": "Parola chiave"}},
    ["query"],
)
async def memory_search(ctx: ToolContext, inp: dict):
    rows = await ctx.hq.store.recall(inp["query"], ctx.company)
    return [{"topic": r["topic"], "content": r["content"], "scope": r["scope"]} for r in rows] or "Nessun ricordo."


@tool(
    "deadline_add",
    "Registra una scadenza (fatture, tasse, consegne, rinnovi, appuntamenti). Jarvis avvisa "
    "l'utente su Telegram il giorno prima.",
    {
        "title": {"type": "string"},
        "due": {"type": "string", "description": "Data ISO, es. 2026-11-30 o 2026-11-30T15:00"},
        "notes": {"type": "string"},
        "company": {"type": "string", "description": "id azienda (solo per Jarvis)"},
    },
    ["title", "due"],
)
async def deadline_add(ctx: ToolContext, inp: dict):
    datetime.fromisoformat(inp["due"])  # validate
    did = await ctx.hq.store.deadline_add(
        inp["title"], inp["due"], ctx.company or inp.get("company"), ctx.agent_id, inp.get("notes", "")
    )
    await ctx.hq.log("deadline", f"Nuova scadenza: {inp['title']} ({inp['due']})", ctx.agent_id)
    await ctx.hq.emit_deadlines()
    return {"ok": True, "id": did}


@tool("deadline_list", "Elenca le scadenze aperte.", {})
async def deadline_list(ctx: ToolContext, inp: dict):
    rows = await ctx.hq.store.deadlines()
    if ctx.company:
        rows = [r for r in rows if r["company"] in (ctx.company, None)]
    return [{k: r[k] for k in ("id", "title", "due", "company", "notes")} for r in rows] or "Nessuna scadenza."


@tool("deadline_done", "Segna una scadenza come completata.", {"id": {"type": "integer"}}, ["id"])
async def deadline_done(ctx: ToolContext, inp: dict):
    await ctx.hq.store.deadline_done(int(inp["id"]))
    await ctx.hq.emit_deadlines()
    return {"ok": True}


@tool(
    "notify_owner",
    "Manda un messaggio Telegram al proprietario. Usalo solo per cose che deve sapere subito "
    "(allarmi, risultati importanti, decisioni da prendere).",
    {"message": {"type": "string"}},
    ["message"],
)
async def notify_owner(ctx: ToolContext, inp: dict):
    name = ctx.hq.agent_name(ctx.agent_id)
    await ctx.hq.notify(f"*{name}*: {inp['message']}")
    return {"ok": True}
