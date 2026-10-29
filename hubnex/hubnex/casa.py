"""The house view: Home Assistant areas and their entities, laid out on the owner's floor plan.

Rooms are Home Assistant areas. The floor plan (`casa.yaml` in the add-on configuration)
only says where each area is drawn; which entities are in a room comes from Home Assistant,
plus the owner's adjustments made in the dashboard ("show this one here too", "hide that").
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from hubnex.integrations.ha_ws import HAWatcher

# Domains shown in the house view, and what kind of control each gets.
KINDS = {
    "light": "light", "switch": "switch", "fan": "switch", "input_boolean": "switch",
    "climate": "climate", "cover": "cover", "media_player": "media", "lock": "lock",
    "alarm_control_panel": "alarm", "scene": "scene", "script": "script", "button": "button",
    "input_button": "button", "sensor": "sensor", "binary_sensor": "binary", "camera": "camera",
    "vacuum": "switch", "water_heater": "climate", "humidifier": "switch", "valve": "cover", "siren": "siren",
}
ATTRS = (
    "friendly_name", "brightness", "rgb_color", "color_mode", "current_temperature", "temperature",
    "target_temp_step", "min_temp", "max_temp", "hvac_modes", "hvac_action", "current_position",
    "unit_of_measurement", "device_class", "media_title", "source", "supported_color_modes",
    "supported_features", "code_format", "code_arm_required",
)
# What the owner can say an entity really is, whatever its Home Assistant domain
# (a relay "switch" that drives a light, a gate opened by an impulse…).
SHOW_AS = {"light", "switch", "gate", "siren", "sensor"}
ALERT_CLASSES = {"door", "window", "opening", "garage_door", "smoke", "moisture", "gas", "safety", "problem", "carbon_monoxide"}

EXAMPLE_LAYOUT = """\
# Piantina della vista Casa. Ogni stanza è un'area di Home Assistant (stesso nome o ID).
# x, y, w, h sono in percentuale del disegno (0-100). Le aree che non compaiono qui
# vengono mostrate sotto la piantina; quelle in "outside" nel gruppo "Fuori casa".
floors:
  - name: Piano terra
    aspect: 1.06        # larghezza / altezza del disegno
    rooms:
      - { area: Soggiorno, x: 0, y: 0, w: 50, h: 60 }
      - { area: Cucina, x: 50, y: 0, w: 50, h: 60 }
      - { area: Camera da letto, x: 0, y: 60, w: 100, h: 40 }
outside: []
# energy: { power: sensor.consumo_casa, today: sensor.energia_oggi }
"""


class LayoutError(ValueError):
    pass


# Italian spellings are accepted too.
ALIASES = {"piani": "floors", "stanze": "rooms", "fuori": "outside", "energia": "energy", "nome": "name",
           "proporzione": "aspect", "contorno": "outline", "potenza": "power", "oggi": "today"}


def _keys(d: dict) -> dict:
    return {ALIASES.get(str(k).lower(), str(k).lower()): v for k, v in d.items()}


def parse_layout(text: str) -> dict:
    """Validated floor plan from YAML; raises LayoutError with a readable message."""
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise LayoutError(f"YAML non valido: {exc}") from exc
    if not isinstance(raw, dict):
        raise LayoutError("il file deve iniziare con floors: (oppure rooms: per un solo piano)")
    raw = _keys(raw)
    if "rooms" in raw and "floors" not in raw:  # a single floor written without "floors:"
        raw["floors"] = [{"name": raw.pop("name", "Piano terra"), "aspect": raw.pop("aspect", None), "rooms": raw.pop("rooms")}]
    unknown = set(raw) - {"floors", "outside", "energy"}
    if unknown:
        raise LayoutError(f"chiave sconosciuta: {', '.join(sorted(unknown))} (valide: floors, outside, energy)")
    if not raw.get("floors"):
        raise LayoutError("nessun piano: manca floors: con almeno una stanza")
    floors = []
    for i, f in enumerate(raw.get("floors") or [], 1):
        if not isinstance(f, dict):
            raise LayoutError(f"piano {i}: formato non valido (controlla i trattini e i rientri)")
        f = _keys(f)
        rooms = []
        for j, r in enumerate(f.get("rooms") or [], 1):
            r = _keys(r) if isinstance(r, dict) else r
            if not isinstance(r, dict) or not (r.get("area") or r.get("label")):
                raise LayoutError(f"piano {i}, stanza {j}: serve 'area'")
            try:
                box = {k: float(r[k]) for k in ("x", "y", "w", "h")}
            except (KeyError, TypeError, ValueError) as exc:
                raise LayoutError(f"piano {i}, stanza {r.get('area')}: servono x, y, w, h numerici") from exc
            if box["w"] <= 0 or box["h"] <= 0 or min(box["x"], box["y"]) < 0 or box["x"] + box["w"] > 100.5 or box["y"] + box["h"] > 100.5:
                raise LayoutError(f"piano {i}, stanza {r.get('area')}: fuori dal disegno (0-100)")
            rooms.append({"area": str(r.get("area") or r.get("label")), **box, "outline": bool(r.get("outline"))})
        aspect = float(f.get("aspect") or 1.4)
        floors.append({"name": str(f.get("name") or f"Piano {i}"), "aspect": max(0.3, min(aspect, 4.0)), "rooms": rooms})
        if not rooms:
            raise LayoutError(f"piano {i}: nessuna stanza (manca rooms:)")
    energy = _keys(raw.get("energy") or {}) if isinstance(raw.get("energy"), dict) else {}
    return {
        "floors": floors,
        "outside": [str(a) for a in raw.get("outside") or []],
        "energy": {k: str(v) for k, v in energy.items() if k in ("power", "today") and v},
    }


class Casa:
    def __init__(self, watcher: "HAWatcher", layout_path: str | Path, store):
        self.ha = watcher
        self.path = Path(layout_path)
        self.store = store
        self.layout = {"floors": [], "outside": [], "energy": {}}
        self.layout_error: str | None = None
        self._mtime: float | None = None
        self.adjust: dict[str, dict[str, list[str]]] = {"extra": {}, "hidden": {}}
        self.shown: set[str] = set()  # entities on screen: only their changes go to the dashboard

    async def load(self) -> None:
        self.adjust = await self.store.get("casa_adjust", {"extra": {}, "hidden": {}})
        self.adjust.setdefault("temp", {})
        self.adjust.setdefault("kind", {})
        self.layout_text()  # parse the saved floor plan

    # ------------------------------------------------------------------ floor plan
    def layout_text(self) -> str:
        if not self.path.exists():
            self.layout, self.layout_error, self._mtime = {"floors": [], "outside": [], "energy": {}}, None, None
            return EXAMPLE_LAYOUT
        self._mtime = self.path.stat().st_mtime
        text = self.path.read_text(encoding="utf-8")
        try:
            self.layout, self.layout_error = parse_layout(text), None
        except LayoutError as exc:
            self.layout_error = str(exc)
        return text

    def host_path(self) -> str:
        """Where the owner finds casa.yaml: /config in the add-on is /addon_configs/<slug>."""
        if str(self.path.parent) == "/config":
            import socket

            return f"/addon_configs/{socket.gethostname().replace('-', '_')}/casa.yaml"
        return str(self.path)

    def save_layout(self, text: str) -> None:
        self.layout = parse_layout(text)  # refuse a broken plan before touching the file
        self.layout_error = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding="utf-8")
        self._mtime = self.path.stat().st_mtime

    # ------------------------------------------------------------------ owner's adjustments
    async def show_here(self, area_id: str, entity_id: str) -> None:
        for other in self.adjust["extra"].values():
            if entity_id in other:
                other.remove(entity_id)
        self.adjust["extra"].setdefault(area_id, []).append(entity_id)
        self._unhide(area_id, entity_id)
        await self.store.put("casa_adjust", self.adjust)

    async def moved_in_ha(self, area_id: str, entity_id: str) -> None:
        self._unhide(area_id, entity_id)
        for other in self.adjust["extra"].values():
            if entity_id in other:
                other.remove(entity_id)
        await self.store.put("casa_adjust", self.adjust)

    async def hide(self, area_id: str, entity_id: str) -> None:
        extra = self.adjust["extra"].get(area_id, [])
        if entity_id in extra:
            extra.remove(entity_id)
        else:
            self.adjust["hidden"].setdefault(area_id, []).append(entity_id)
        await self.store.put("casa_adjust", self.adjust)

    async def set_temperature(self, area_id: str, entity_id: str | None) -> None:
        """The sensor that gives the room its temperature (None: let the view choose)."""
        temp = self.adjust.setdefault("temp", {})
        if entity_id:
            temp[area_id] = entity_id
        else:
            temp.pop(area_id, None)
        await self.store.put("casa_adjust", self.adjust)

    async def set_kind(self, entity_id: str, kind: str | None) -> None:
        """Show an entity as another kind in the dashboard (None: as Home Assistant says)."""
        kinds = self.adjust.setdefault("kind", {})
        if kind:
            if kind not in SHOW_AS:
                raise ValueError(f"tipo sconosciuto: {kind}")
            kinds[entity_id] = kind
        else:
            kinds.pop(entity_id, None)
        await self.store.put("casa_adjust", self.adjust)

    def _unhide(self, area_id: str, entity_id: str) -> None:
        hidden = self.adjust["hidden"].get(area_id, [])
        if entity_id in hidden:
            hidden.remove(entity_id)

    # ------------------------------------------------------------------ building the view
    def visible(self, entity_id: str) -> bool:
        domain = entity_id.split(".", 1)[0]
        if domain not in KINDS:
            return False
        reg = self.ha.entities.get(entity_id) or {}
        return not (reg.get("disabled_by") or reg.get("hidden_by") or reg.get("entity_category"))

    def compact(self, entity_id: str, state: dict | None = None) -> dict | None:
        s = state if state is not None else self.ha.states.get(entity_id)
        if not s:
            return None
        attrs = s.get("attributes") or {}
        reg = self.ha.entities.get(entity_id) or {}
        name = reg.get("name") or attrs.get("friendly_name") or reg.get("original_name") or entity_id
        native = KINDS.get(entity_id.split(".", 1)[0], "other")
        shown = self.adjust.get("kind", {}).get(entity_id)
        out = {
            "s": s.get("state"),
            "n": name,
            "k": shown or native,
            "a": {k: attrs[k] for k in ATTRS if k in attrs and k != "friendly_name"},
        }
        if shown:
            out["nk"] = native  # what Home Assistant says it is
        return out

    def area_entities(self) -> dict[str, list[str]]:
        rooms: dict[str, list[str]] = {a: [] for a in self.ha.areas}
        for eid in self.ha.states:
            area = self.ha.area_of(eid)
            if area in rooms and self.visible(eid):
                rooms[area].append(eid)
        for area, eids in self.adjust["extra"].items():
            for eid in eids:
                if area in rooms and eid in self.ha.states and eid not in rooms[area]:
                    rooms[area].append(eid)
        for area, eids in self.adjust["hidden"].items():
            if area in rooms:
                rooms[area] = [e for e in rooms[area] if e not in eids]
        return rooms

    def _area_id(self, ref: str) -> str | None:
        if ref in self.ha.areas:
            return ref
        low = ref.strip().lower()
        return next((a for a, v in self.ha.areas.items() if (v.get("name") or "").strip().lower() == low), None)

    def _refresh_layout(self) -> None:
        """Pick up a casa.yaml edited by hand (File editor, Samba) without a restart."""
        mtime = self.path.stat().st_mtime if self.path.exists() else None
        if mtime != self._mtime:
            self.layout_text()

    def build(self) -> dict:
        self._refresh_layout()
        rooms = self.area_entities()
        floors, placed = [], set()
        for f in self.layout["floors"]:
            drawn = []
            for r in f["rooms"]:
                aid = self._area_id(r["area"])
                if aid:
                    placed.add(aid)
                drawn.append({**r, "area_id": aid, "name": self.ha.areas[aid]["name"] if aid else r["area"]})
            floors.append({**f, "rooms": drawn})
        outside_ids = [a for a in (self._area_id(x) for x in self.layout["outside"]) if a]
        placed.update(outside_ids)
        areas = [
            {
                "id": aid,
                "name": a.get("name") or aid,
                "floor": (self.ha.floors.get(a.get("floor_id") or "") or {}).get("name"),
                "entities": sorted(rooms.get(aid, []), key=lambda e: (e.split(".", 1)[0], e)),
                "outside": aid in outside_ids,
                "temp": self.adjust.get("temp", {}).get(aid),
                "placed": aid in placed,
            }
            for aid, a in sorted(self.ha.areas.items(), key=lambda kv: (kv[1].get("name") or "").lower())
        ]
        scenes = sorted(e for e in self.ha.states if e.startswith("scene.") and self.visible(e))
        # The alarm is for the whole house: always reachable, with or without an area.
        alarms = sorted(e for e in self.ha.states if e.startswith("alarm_control_panel.") and self.visible(e))
        weather = next((e for e in sorted(self.ha.states) if e.startswith("weather.")), None)
        energy = {k: v for k, v in self.layout["energy"].items() if v in self.ha.states}
        shown = {e for a in areas for e in a["entities"]} | set(scenes) | set(alarms) | set(energy.values())
        if weather:
            shown.add(weather)
        self.shown = shown
        states = {e: self.compact(e) for e in shown}
        return {
            "ready": self.ha.ready.is_set(),
            "floors": floors,
            "areas": areas,
            "scenes": scenes,
            "alarms": alarms,
            "weather": weather,
            "energy": energy,
            "states": {e: s for e, s in states.items() if s},
            "layout_error": self.layout_error,
            "layout_file": self.host_path(),
        }

    def candidates(self, query: str = "", area_id: str | None = None, limit: int = 40) -> list[dict[str, Any]]:
        """Entities that could be added to a room, for the dashboard's search."""
        q = query.strip().lower()
        here = set(self.area_entities().get(area_id or "", []))
        out = []
        for eid in sorted(self.ha.states):
            if eid in here or not self.visible(eid):
                continue
            c = self.compact(eid)
            if q and q not in f"{eid} {c['n']}".lower():
                continue
            area = self.ha.area_of(eid)
            out.append({
                "entity_id": eid,
                "name": c["n"],
                "area": (self.ha.areas.get(area) or {}).get("name") if area else None,
                "registered": eid in self.ha.entities,
            })
            if len(out) >= limit:
                break
        return out
