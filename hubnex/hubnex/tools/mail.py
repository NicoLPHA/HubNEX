"""Work mailbox tools (ported from the original Jarvis Mail). Nothing is ever sent from here:
replies become drafts that the owner approves with the Telegram buttons."""

from __future__ import annotations

import asyncio

from hubnex.tools import ToolContext, tool


def _mail(ctx: ToolContext):
    if ctx.hq.maildesk is None:
        raise RuntimeError("Casella email non configurata (mail_user / mail_password).")
    return ctx.hq.maildesk.client


@tool(
    "mail_list",
    "Elenca le email più recenti della posta in arrivo (mittente, oggetto, data, anteprima, uid).",
    {
        "solo_non_lette": {"type": "boolean", "description": "true = solo non lette"},
        "quante": {"type": "integer", "description": "quante email (max 30)"},
    },
)
async def mail_list(ctx: ToolContext, inp: dict):
    r = await asyncio.to_thread(_mail(ctx).list_emails, bool(inp.get("solo_non_lette")), int(inp.get("quante") or 10))
    return r or "Nessuna email."


@tool(
    "mail_search",
    "Cerca nella posta in arrivo per mittente, oggetto o testo.",
    {"testo": {"type": "string"}, "quante": {"type": "integer"}},
    ["testo"],
)
async def mail_search(ctx: ToolContext, inp: dict):
    r = await asyncio.to_thread(_mail(ctx).search, inp["testo"], int(inp.get("quante") or 10))
    return r or "Nessun risultato."


@tool(
    "mail_read",
    "Legge il testo completo di una email dato il suo uid.",
    {"uid": {"type": "integer"}},
    ["uid"],
)
async def mail_read(ctx: ToolContext, inp: dict):
    r = await asyncio.to_thread(_mail(ctx).get_email, int(inp["uid"]))
    r.pop("references", None)
    return r


@tool(
    "mail_propose_draft",
    "Prepara una bozza di risposta a una email e la mostra al proprietario con i pulsanti "
    "Invia / Salva in Bozze / Modifica / Scarta. NON invia nulla.",
    {
        "uid": {"type": "integer", "description": "uid dell'email a cui rispondere"},
        "testo": {"type": "string", "description": "corpo della risposta, senza firma"},
        "rispondi_a_tutti": {"type": "boolean"},
    },
    ["uid", "testo"],
)
async def mail_propose_draft(ctx: ToolContext, inp: dict):
    _mail(ctx)
    return await ctx.hq.maildesk.propose_draft(int(inp["uid"]), inp["testo"], bool(inp.get("rispondi_a_tutti")))
