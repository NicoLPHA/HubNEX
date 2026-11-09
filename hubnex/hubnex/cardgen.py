"""A free card described in words: Claude composes it from the house's real entities.

One request, structured output: the card comes back as JSON that the dashboard's editor opens,
for the owner to check and save. Only entities that exist reach the editor.
"""

from __future__ import annotations

from typing import Any

KINDS = ["value", "ring", "toggle", "button", "slider", "chart", "bar", "band", "select", "state", "text", "camera", "media", "ask"]
COLORS = ["", "warm", "cool", "green", "violet", "red"]
OPS = ["<", ">", "=", "!="]

_cmp = {
    "type": "object",
    "properties": {"op": {"type": "string", "enum": OPS}, "v": {"type": "string"}},
    "required": ["op", "v"],
    "additionalProperties": False,
}
CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "color": {"type": "string", "enum": COLORS},
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": KINDS},
                    "entity": {"type": "string"},
                    "entity2": {"type": "string"},
                    "label": {"type": "string"},
                    "w": {"type": "integer", "enum": [1, 2, 3, 4]},
                    "h": {"type": "integer", "enum": [1, 2]},
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                    "rules": {"type": "array", "items": {
                        "type": "object",
                        "properties": {**_cmp["properties"], "c": {"type": "string", "enum": COLORS[1:]}},
                        "required": ["op", "v", "c"], "additionalProperties": False,
                    }},
                    "show": {"type": "object", "properties": {"e": {"type": "string"}, **_cmp["properties"]},
                             "required": ["e", "op", "v"], "additionalProperties": False},
                    "tap": {"type": "object", "properties": {
                        "do": {"type": "string", "enum": ["toggle", "run", "ask", "room"]},
                        "e": {"type": "string"}, "text": {"type": "string"}, "area": {"type": "string"},
                    }, "required": ["do"], "additionalProperties": False},
                },
                "required": ["kind", "entity", "label", "w", "h"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["name", "color", "blocks"],
    "additionalProperties": False,
}

SYSTEM = (
    "Componi card per la dashboard di una casa con Home Assistant. Rispondi solo con la card, "
    "usando esclusivamente gli entity_id dell'elenco che ricevi: mai inventarne."
)

GUIDE = """Una card è una griglia di 4 colonne; ogni blocco occupa w colonne (1-4) e h righe (1-2).
Blocchi (kind) e l'entità che vogliono:
- value: un valore o uno stato in grande (qualsiasi; clima: la temperatura) — spesso 2x1 o 2x2
- ring: indicatore ad anello di un numero; min e max della scala se non ovvi (umidità 0-100)
- toggle: interruttore di luce, presa, interruttore (kind switch o light)
- button: avvia una scena, uno script o un pulsante
- slider: luminosità di una luce o un numero impostabile
- chart: grafico delle ultime 24 ore di un sensore numerico — di solito 4x1 o 2x1
- bar: quanto è pieno (scorte, livelli); min e max se servono
- band: fascia oraria: entity = orario di inizio, entity2 = orario di fine (kind datetime) — 4x1
- select: scelta tra opzioni (kind select)
- state: com'è e da quanto (porte, finestre, serrature, sensori di presenza, persone)
- camera: l'immagine della telecamera — 2x2 o 4x2
- media: copertina e comandi di un lettore — 2x1 o 4x1
- ask: una domanda pronta per l'assistente; la domanda va in label, entity vuoto
- text: un titolo o una nota in label, entity vuoto
Per ogni blocco puoi aggiungere, solo se utili a quello che chiede l'utente:
- rules: colore secondo il valore (op < > = !=, v, c tra warm cool green violet red), es. temperatura sopra 23 → red
- show: il blocco compare solo se l'entità e confronta op con v, es. {"e": "binary_sensor.x", "op": "=", "v": "on"}
- tap: cosa fa un tocco: toggle (e: cosa), run (e: scena o script), ask (text: la domanda), room (area: id della stanza)
I valori di confronto sono quelli di Home Assistant: on, off, open, closed, playing, home, locked… o numeri.
label vuota = il nome dell'entità. Il colore della card (color) si sceglie dal tema: stufa e calore warm,
acqua e clima cool, energia green, musica violet, sicurezza red; "" se nessuno.
Disponi i blocchi nell'ordine in cui si leggono, riempiendo le righe da 4 colonne senza buchi."""


def entity_lines(casa, area_id: str, limit: int = 220) -> list[str]:
    """The house as the model reads it: the room's entities first, then the useful ones elsewhere."""
    useful = {"climate", "camera", "media", "datetime", "select", "number", "stock", "scene", "script",
              "button", "lock", "light", "switch", "cover", "vacuum", "alarm", "person"}
    room = casa.area_entities().get(area_id, [])
    rest = [e for e in sorted(casa.ha.states) if e not in room]
    out: list[str] = []
    for e in [*room, *rest]:
        c = casa.compact(e)
        if not c:
            continue
        a = c["a"]
        if e not in room and c["k"] not in useful and not (
            c["k"] in ("sensor", "binary") and a.get("device_class")
        ):
            continue
        area = casa.ha.area_of(e)
        where = (casa.ha.areas.get(area) or {}).get("name", "") if area else ""
        extra = f" opzioni={a['options']}" if a.get("options") else ""
        dc = f" ({a['device_class']})" if a.get("device_class") else ""
        out.append(f"{e} | {c['n']} | {c['k']}{dc} | {c['s']}{a.get('unit_of_measurement', '')}{extra} | {where}")
        if len(out) >= limit:
            break
    return out


def card_prompt(room_name: str, lines: list[str], request: str, rooms: list[tuple[str, str]]) -> str:
    areas = ", ".join(f"{i} ({n})" for i, n in rooms)
    return (
        f"{GUIDE}\n\nLa card va nella stanza «{room_name}». Stanze (per tap room): {areas}.\n\n"
        f"Entità (entity_id | nome | tipo | stato | area), prima quelle della stanza:\n"
        + "\n".join(lines)
        + f"\n\nRichiesta dell'utente:\n{request.strip()}"
    )
