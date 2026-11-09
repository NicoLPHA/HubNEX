"""More for the house: history from Home Assistant's recorder (read only), light scenes remembered by
HubNEX itself, and the shopping list. Nothing here writes to Home Assistant's configuration."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from hubnex.context import ORIGIN
from hubnex.tools import ToolContext, tool
from hubnex.tools.homeassistant import _clip, _ha

MAX_HISTORY_ENTITIES = 5
MAX_HISTORY_HOURS = 24 * 7  # the recorder keeps ten days by default
SCENE_DOMAINS = ("light", "switch")  # a scene only remembers lights and plugs
SCENE_KEY = "jarvis_scenes"
MAX_SCENES = 30
MAX_ITEMS = 20
LIGHT_ATTRS = ("brightness", "color_temp_kelvin", "rgb_color")


def _owner_only(what: str) -> None:
    if ORIGIN.get() != "owner":
        # Routines and automation events can look and report, never act on their own.
        raise PermissionError(
            f"{what}: questo lavoro non l'ha chiesto l'utente ({ORIGIN.get()}). "
            "Riferisci cosa hai trovato e proponi cosa fare con notify_owner."
        )


# ------------------------------------------------------------------------------ history
def _num(value):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def summarize(series: list[tuple[str, str]], unit: str = "") -> dict:
    """A compact summary of one entity's state changes (so Claude gets a few numbers, not the whole list)."""
    rows = [(t, s) for t, s in series if s not in (None, "")]
    if not rows:
        return {"nota": "nessun dato nel periodo"}
    values = [_num(s) for _, s in rows]
    nums = [v for v in values if v is not None]
    if len(nums) >= max(2, len(rows) * 0.8):  # a measurement: temperature, power…
        k = max(range(len(nums)), key=nums.__getitem__)
        lo = min(range(len(nums)), key=nums.__getitem__)
        times = [t for (t, _), v in zip(rows, values) if v is not None]
        return {
            "tipo": "misura", "unità": unit, "ora": round(nums[-1], 2),
            "minimo": {"valore": round(nums[lo], 2), "alle": times[lo]},
            "massimo": {"valore": round(nums[k], 2), "alle": times[k]},
            "media": round(sum(nums) / len(nums), 2), "letture": len(nums),
        }
    counts: dict[str, int] = {}
    prev = rows[0][1]  # the first row is the state at the start of the period: it did not "become" it
    for _, s in rows[1:]:
        if s != prev:
            counts[s] = counts.get(s, 0) + 1  # how many times it BECAME this state
        prev = s
    changes = [{"alle": t, "stato": s} for t, s in rows]
    out = {"tipo": "stati", "volte_in_stato": counts, "ora": rows[-1][1], "cambi": len(rows) - 1}
    if len(changes) > 30:
        out["ultimi_cambi"] = changes[-30:]
        out["troncato"] = True
    else:
        out["cambi_dettaglio"] = changes
    return out


@tool(
    "ha_history",
    "Storico di Home Assistant (solo lettura): come è cambiato un sensore o un apparecchio nelle ultime ore o "
    "giorni. Per una misura (temperatura, potenza) dà minimo, massimo, media; per uno stato (porta, luce, "
    "presenza) dà quante volte è diventato aperto/acceso ecc. Esempi: «quante volte si è aperta la porta sul "
    "retro questa settimana», «che temperatura c'era ieri in salotto». Massimo 5 entità e 7 giorni.",
    {
        "entity_ids": {"type": "array", "items": {"type": "string"}, "description": "es. [\"binary_sensor.porta_retro\"]"},
        "hours": {"type": "integer", "description": "quante ore indietro (1-168, predefinito 24)"},
    },
    ["entity_ids"],
)
async def ha_history(ctx: ToolContext, inp: dict):
    ha = _ha(ctx)
    ids = [e for e in (inp.get("entity_ids") or []) if isinstance(e, str) and re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", e)]
    if not ids:
        return {"errore": "Indica almeno un entity_id valido (usa ha_list_entities per trovarlo)."}
    if len(ids) > MAX_HISTORY_ENTITIES:
        ids = ids[:MAX_HISTORY_ENTITIES]
    try:
        hours = max(1, min(MAX_HISTORY_HOURS, int(inp.get("hours") or 24)))
    except (TypeError, ValueError):
        hours = 24
    data = await ha.history(ids, hours)
    states = ctx.hq.watcher.states
    out = {}
    for eid in ids:
        attrs = (states.get(eid) or {}).get("attributes") or {}
        entry = summarize(data.get(eid, []), attrs.get("unit_of_measurement", ""))
        entry["naam"] = attrs.get("friendly_name") or eid
        out[eid] = entry
    return {"ore": hours, "entità": out}


# ------------------------------------------------------------------------------ scenes
def _slug(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().lower())[:40]


def _snapshot(state: dict) -> dict:
    """What it takes to bring one light or plug back as it is now."""
    attrs = state.get("attributes") or {}
    if state.get("state") != "on":
        return {"state": "off"}
    snap: dict = {"state": "on"}
    if "brightness" in attrs and attrs["brightness"] is not None:
        snap["brightness"] = attrs["brightness"]
    mode = attrs.get("color_mode")
    if mode == "color_temp" and attrs.get("color_temp_kelvin"):
        snap["color_temp_kelvin"] = attrs["color_temp_kelvin"]
    elif mode in ("rgb", "rgbw", "rgbww", "hs", "xy") and attrs.get("rgb_color"):
        snap["rgb_color"] = list(attrs["rgb_color"])[:3]
    return snap


@tool(
    "ha_scene_save",
    "Ricorda come sono ADESSO le luci (e le prese) come scena con un nome, per esempio «serata film». "
    "Senza `entities` salva tutte le luci. Richiamala con ha_scene_apply. Una scena con lo stesso nome "
    "viene sostituita. Non scrive nulla nella configurazione di Home Assistant.",
    {
        "name": {"type": "string", "description": "nome della scena, es. 'serata film'"},
        "entities": {"type": "array", "items": {"type": "string"},
                     "description": "entity_id di luci/prese da includere; vuoto = tutte le luci"},
    },
    ["name"],
)
async def ha_scene_save(ctx: ToolContext, inp: dict):
    _owner_only("non puoi salvare scene")
    _ha(ctx)
    key = _slug(inp.get("name"))
    if not key:
        return {"errore": "Serve un nome per la scena."}
    states = ctx.hq.watcher.states
    wanted = [e for e in (inp.get("entities") or []) if isinstance(e, str)]
    if wanted:
        ids = [e for e in wanted if e.split(".")[0] in SCENE_DOMAINS and e in states]
        skipped = [e for e in wanted if e not in ids]
    else:
        ids = sorted(e for e in states if e.startswith("light."))
        skipped = []
    if not ids:
        return {"errore": "Nessuna luce o presa trovata da salvare.", "scartate": skipped}
    scenes = await ctx.hq.store.get(SCENE_KEY, {}) or {}
    if key not in scenes and len(scenes) >= MAX_SCENES:
        return {"errore": f"Troppe scene (massimo {MAX_SCENES}): cancellane una con ha_scene_delete."}
    scenes[key] = {
        "name": _clip(inp.get("name"), 40), "saved": datetime.now(timezone.utc).isoformat(),
        "entities": {e: _snapshot(states[e]) for e in ids},
    }
    await ctx.hq.store.put(SCENE_KEY, scenes)
    await ctx.hq.log("ha", f"scena salvata: {key} ({len(ids)} apparecchi)", ctx.agent_id)
    out = {"ok": True, "scena": scenes[key]["name"], "apparecchi": len(ids)}
    if skipped:
        out["scartate"] = skipped
    return out


@tool(
    "ha_scene_list",
    "Elenca le scene che HubNEX ha salvato con ha_scene_save (nome e numero di apparecchi).",
    {},
)
async def ha_scene_list(ctx: ToolContext, inp: dict):
    scenes = await ctx.hq.store.get(SCENE_KEY, {}) or {}
    return [{"scena": s["name"], "apparecchi": len(s["entities"]), "salvata": s["saved"]} for s in scenes.values()] or \
        "Nessuna scena salvata."


@tool(
    "ha_scene_apply",
    "Richiama una scena salvata con ha_scene_save: rimette le luci come erano. Cambia lo stato della casa.",
    {"name": {"type": "string"}},
    ["name"],
)
async def ha_scene_apply(ctx: ToolContext, inp: dict):
    _owner_only("non puoi cambiare nulla in casa")
    ha = _ha(ctx)
    scenes = await ctx.hq.store.get(SCENE_KEY, {}) or {}
    scene = scenes.get(_slug(inp.get("name")))
    if not scene:
        return {"errore": "Scena non trovata.", "disponibili": [s["name"] for s in scenes.values()]}
    done, failed = 0, []
    for eid, snap in scene["entities"].items():
        domain = eid.split(".")[0]
        if domain not in SCENE_DOMAINS:
            continue  # a stored entry is never trusted to name another domain
        try:
            if snap.get("state") != "on":
                await ha.call_service(domain, "turn_off", {"entity_id": eid})
            else:
                data = {"entity_id": eid}
                if domain == "light":
                    data.update({k: snap[k] for k in LIGHT_ATTRS if k in snap})
                await ha.call_service(domain, "turn_on", data)
            done += 1
        except Exception as exc:  # one unreachable lamp must not stop the others
            failed.append({"entity_id": eid, "errore": str(exc)[:120]})
    await ctx.hq.log("ha", f"scena richiamata: {scene['name']} ({done} apparecchi)", ctx.agent_id)
    out = {"ok": not failed, "scena": scene["name"], "apparecchi_cambiati": done}
    if failed:
        out["non_riusciti"] = failed
    return out


@tool(
    "ha_scene_delete",
    "Cancella una scena salvata con ha_scene_save.",
    {"name": {"type": "string"}},
    ["name"],
)
async def ha_scene_delete(ctx: ToolContext, inp: dict):
    _owner_only("non puoi cancellare scene")
    scenes = await ctx.hq.store.get(SCENE_KEY, {}) or {}
    key = _slug(inp.get("name"))
    if key not in scenes:
        return {"errore": "Scena non trovata.", "disponibili": [s["name"] for s in scenes.values()]}
    gone = scenes.pop(key)
    await ctx.hq.store.put(SCENE_KEY, scenes)
    return {"ok": True, "cancellata": gone["name"]}


# ------------------------------------------------------------------------------ shopping list
def _shopping_entity(ctx: ToolContext, named: str | None) -> tuple[str | None, dict | None]:
    """The to-do list to use: the one asked for, `todo.shopping_list`, or the only one there is."""
    todos = sorted(e for e in ctx.hq.watcher.states if e.startswith("todo."))
    if named:
        if named in todos:
            return named, None
        return None, {"errore": f"Lista non trovata: {named}", "disponibili": todos}
    if "todo.shopping_list" in todos:
        return "todo.shopping_list", None
    if len(todos) == 1:
        return todos[0], None
    if not todos:
        return None, {"errore": "Home Assistant non ha nessuna lista (attiva l'integrazione «Lista della spesa»)."}
    return None, {"errore": "Quale lista? Indica `list`.", "disponibili": todos}


@tool(
    "ha_shopping_list",
    "Legge la lista della spesa di Home Assistant: cosa c'è ancora da comprare. Solo lettura.",
    {"list": {"type": "string", "description": "entity_id della lista, predefinito todo.shopping_list"}},
)
async def ha_shopping_list(ctx: ToolContext, inp: dict):
    ha = _ha(ctx)
    eid, err = _shopping_entity(ctx, inp.get("list"))
    if err:
        return err
    items = await ha.todo_items(eid)
    names = [_clip(i.get("summary"), 100) for i in items][:100]
    return {"lista": eid, "da_comprare": names} if names else f"La lista {eid} è vuota."


@tool(
    "ha_shopping_add",
    "Aggiunge cose alla lista della spesa di Home Assistant (una voce per prodotto, es. «latte», «pane»). "
    "Quelle già presenti non vengono ripetute. Massimo 20 voci per volta.",
    {
        "items": {"type": "array", "items": {"type": "string"}, "description": "es. [\"latte\", \"pane\"]"},
        "list": {"type": "string", "description": "entity_id della lista, predefinito todo.shopping_list"},
    },
    ["items"],
)
async def ha_shopping_add(ctx: ToolContext, inp: dict):
    _owner_only("non puoi cambiare la lista")
    ha = _ha(ctx)
    eid, err = _shopping_entity(ctx, inp.get("list"))
    if err:
        return err
    wanted = []
    for raw in inp.get("items") or []:
        item = _clip(raw, 100).strip()
        if item and item.lower() not in {w.lower() for w in wanted}:
            wanted.append(item)
    if not wanted:
        return {"errore": "Nessuna voce da aggiungere."}
    wanted = wanted[:MAX_ITEMS]
    have = {str(i.get("summary") or "").strip().lower() for i in await ha.todo_items(eid)}
    added, existing = [], []
    for item in wanted:
        if item.lower() in have:
            existing.append(item)
            continue
        await ha.call_service("todo", "add_item", {"entity_id": eid, "item": item})
        added.append(item)
    await ctx.hq.log("ha", f"lista della spesa {eid}: aggiunto {', '.join(added) or '-'}", ctx.agent_id)
    out = {"ok": True, "lista": eid, "aggiunte": added}
    if existing:
        out["già_presenti"] = existing
    return out
