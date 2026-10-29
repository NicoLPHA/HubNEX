from __future__ import annotations

from hubnex.context import ORIGIN
from hubnex.tools import ToolContext, tool


def _ha(ctx: ToolContext):
    if not ctx.hq.ha.enabled:
        raise RuntimeError("Home Assistant non configurato (HA_URL / HA_TOKEN).")
    return ctx.hq.ha


@tool(
    "ha_list_entities",
    "Elenca le entità di Home Assistant con il loro stato. Filtra per dominio (light, switch, "
    "climate, sensor, cover, media_player...) e/o per testo nel nome. Usalo prima di agire se "
    "non conosci l'entity_id esatto.",
    {
        "domain": {"type": "string", "description": "Dominio, es. 'light'"},
        "search": {"type": "string", "description": "Testo da cercare in entity_id o nome, es. 'cucina'"},
    },
)
async def ha_list_entities(ctx: ToolContext, inp: dict):
    entities = await _ha(ctx).list_entities(inp.get("domain"), inp.get("search"))
    if len(entities) > 150:
        return {"totale": len(entities), "prime_150": entities[:150], "nota": "Restringi la ricerca."}
    return entities


@tool(
    "ha_get_state",
    "Legge lo stato completo (con attributi) di un'entità di Home Assistant.",
    {"entity_id": {"type": "string"}},
    ["entity_id"],
)
async def ha_get_state(ctx: ToolContext, inp: dict):
    return await _ha(ctx).get_state(inp["entity_id"])


@tool(
    "ha_call_service",
    "Chiama un servizio di Home Assistant, es. light.turn_on, climate.set_temperature, "
    "script.turn_on, notify.mobile_app_xxx. `data` contiene entity_id e i parametri del servizio.",
    {
        "domain": {"type": "string"},
        "service": {"type": "string"},
        "data": {"type": "object", "description": "es. {\"entity_id\": \"light.salotto\", \"brightness_pct\": 40}"},
    },
    ["domain", "service"],
)
async def ha_call_service(ctx: ToolContext, inp: dict):
    if ORIGIN.get() != "owner":
        # Routines and automation events can look and report, never act on their own.
        raise PermissionError(
            "non puoi cambiare nulla in casa: questo lavoro non l'ha chiesto l'utente "
            f"({ORIGIN.get()}). Riferisci cosa hai trovato e proponi cosa fare con notify_owner."
        )
    changed = await _ha(ctx).call_service(inp["domain"], inp["service"], inp.get("data") or {})
    await ctx.hq.log("ha", f"{inp['domain']}.{inp['service']} {inp.get('data') or ''}", ctx.agent_id)
    return {"ok": True, "entità_cambiate": changed}
