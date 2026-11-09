"""Learned shortcuts: a question that keeps coming back is answered locally.

The quick route (Haiku) answers a house question by calling a few tools. When the same question (exactly, after
dropping capitals and punctuation) was answered three times with the same tool calls, those calls are remembered.
The next time HubNEX runs the tools itself and phrases the result in a fixed sentence: no AI, no waiting.

Safe by construction:
  - only read-only tools and saved scenes are learned (never locks, alarm, doors, free service calls);
  - only the owner's questions, never routines or events;
  - an unexpected result (error, an entity that is gone) falls back to Claude, and a shortcut that fails three
    times in a row is dropped and learned again;
  - a time word in the question ("vandaag", "deze week") is recomputed every time.
The shortcuts live in HubNEX's own store; the owner can see, remove and switch them off in the dashboard."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timezone

from hubnex.context import ORIGIN
from hubnex.i18n import system_lang, tr_sys
from hubnex.tools import REGISTRY, ToolContext

log = logging.getLogger("hubnex.shortcuts")

KEY = "shortcuts"
ENABLED_KEY = "shortcuts_enabled"
THRESHOLD = 3  # the same question with the same tool calls this many times
MAX_FAILS = 3
MAX_ENTRIES = 200
MAX_STEPS = 3

DISCOVERY = {"ha_list_entities"}  # only looks things up: the plan keeps the entity ids it found
READ = {"ha_history", "ha_get_state", "ha_shopping_list", "ha_scene_list"}
ACT = {"ha_scene_apply"}
LEARNABLE = READ | ACT

# A question that leans on the one before ("en in de keuken?", "en gisteren?") means nothing on its own.
FOLLOW_UP = re.compile(
    r"^(en|ook|en dan|maar|and|also|e|anche)\b|\b(daar|die|dat|dit|hem|haar|hetzelfde|ervan|erover|there|that|it|lì|quello)\b", re.I)
YESTERDAY = re.compile(r"\b(gisteren|eergisteren|gisteravond|vorige week|yesterday|ieri)\b", re.I)
PERIODS = [  # (pattern, period): "today" runs from midnight, a number is that many hours
    (re.compile(r"\b(vandaag|today|oggi)\b", re.I), "today"),
    (re.compile(r"\b(het |de )?(afgelopen|laatste) uur\b|\blast hour\b|\bultima ora\b", re.I), 1),
    (re.compile(r"\b(afgelopen|laatste) (24 uur|etmaal|dag)\b|\b(past|last) 24 hours\b|\bultime 24 ore\b", re.I), 24),
    (re.compile(r"\b(deze|afgelopen|laatste) week\b|\b7 dagen\b|\bzeven dagen\b|\b(this|past|last) week\b|\bquesta settimana\b", re.I), 168),
]


def normalize(text: str) -> str:
    """The question without capitals, punctuation and extra spaces. The dashboard's room note stays in: "is het
    licht aan?" means something else in the kitchen than in the hall."""
    t = re.sub(r"[^\w\s\[\]]", " ", str(text).lower())
    return re.sub(r"\s+", " ", t).strip()[:240]


def period_of(text: str):
    """None (nothing said), "today", an hour count, or False (a period that cannot be recomputed)."""
    if YESTERDAY.search(text):
        return False
    for pattern, period in PERIODS:
        if pattern.search(text):
            return period
    return None


def hours_for(period, now: datetime) -> int:
    if period == "today":
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, min(168, math.ceil((now - midnight).total_seconds() / 3600)))
    return int(period)


def plan_of(text: str, calls: list[tuple[str, dict, bool, str]]) -> list[dict] | None:
    """The tool calls worth remembering, or None when this answer cannot become a shortcut."""
    if FOLLOW_UP.search(re.sub(r"^\s*\[[^\]]*\]\s*", "", text)) or len(normalize(text).split()) < 3:
        return None
    plan = []
    for name, inp, error, out in calls:
        if error or '"errore"' in str(out)[:200]:
            return None
        if name in DISCOVERY:
            continue
        if name not in LEARNABLE:
            return None
        step: dict = {"tool": name}
        if name == "ha_history":
            ids = sorted(e for e in (inp.get("entity_ids") or []) if isinstance(e, str))
            if not ids:
                return None
            step["input"] = {"entity_ids": ids}
            said = period_of(text)
            if said is False:
                return None
            hours = inp.get("hours")
            if said is not None:
                step["period"] = said
            elif hours in (None, 24):
                step["period"] = 24
            else:
                return None  # an hour count that the question does not explain
        elif name == "ha_get_state":
            if not isinstance(inp.get("entity_id"), str):
                return None
            step["input"] = {"entity_id": inp["entity_id"]}
        elif name == "ha_shopping_list":
            step["input"] = {k: v for k, v in inp.items() if k == "list" and isinstance(v, str)}
        elif name == "ha_scene_list":
            step["input"] = {}
        else:  # ha_scene_apply
            if not isinstance(inp.get("name"), str):
                return None
            step["input"] = {"name": inp["name"]}
        plan.append(step)
    return plan if 1 <= len(plan) <= MAX_STEPS else None


# ------------------------------------------------------------------------------ phrasing of the results
def _num(x) -> str:
    s = f"{round(float(x), 1):g}"
    return s.replace(".", ",") if system_lang() in ("nl", "it") else s


def _states() -> dict[str, str]:
    return {
        "on": tr_sys("acceso"), "off": tr_sys("spento"), "open": tr_sys("aperto"), "closed": tr_sys("chiuso"),
        "unavailable": tr_sys("non raggiungibile"), "home": tr_sys("a casa"), "not_home": tr_sys("fuori casa"),
    }


def _period_label(period, hours: int) -> str:
    if period == "today":
        return tr_sys("oggi")
    if hours % 24 == 0 and hours >= 48:
        return tr_sys("ultimi {d} giorni", d=hours // 24)
    return tr_sys("ultime {h} ore", h=hours)


def _clock(stamp: str, tz, long: bool) -> str:
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(tz).strftime("%d-%m %H:%M" if long else "%H:%M")
    except ValueError:
        return str(stamp)


def phrase(tool: str, out, step: dict, hq) -> str | None:
    """The result in a fixed sentence, or None when it is not what was expected (Claude takes it then)."""
    states = _states()
    if tool == "ha_history":
        if not isinstance(out, dict) or "entità" not in out:
            return None
        hours = int(out.get("ore") or 24)
        label = _period_label(step.get("period"), hours)
        long = hours > 24
        lines = []
        for entry in out["entità"].values():
            name = entry.get("naam", "?")
            if entry.get("tipo") == "misura":
                u = entry.get("unità") or ""
                lines.append(tr_sys(
                    "{name}: ora {now}{u}, minimo {lo}{u} alle {lot}, massimo {hi}{u} alle {hit}, media {avg}{u} ({period}).",
                    name=name, now=_num(entry["ora"]), u=(" " + u) if u else "", lo=_num(entry["minimo"]["valore"]),
                    lot=_clock(entry["minimo"]["alle"], hq.tz, long), hi=_num(entry["massimo"]["valore"]),
                    hit=_clock(entry["massimo"]["alle"], hq.tz, long), avg=_num(entry["media"]), period=label))
            elif entry.get("tipo") == "stati":
                counts = entry.get("volte_in_stato") or {}
                said = ", ".join(tr_sys("{n} volte {state}", n=n, state=states.get(s, s)) for s, n in counts.items()) \
                    or tr_sys("nessun cambiamento")
                lines.append(tr_sys("{name}: {counts} ({period}); ora {now}.", name=name, counts=said, period=label,
                                    now=states.get(entry.get("ora"), entry.get("ora"))))
            else:
                lines.append(tr_sys("{name}: nessun dato ({period}).", name=name, period=label))
        return "\n".join(lines) or None
    if tool == "ha_get_state":
        if not isinstance(out, dict) or "state" not in out:
            return None
        attrs = out.get("attributes") or {}
        unit = attrs.get("unit_of_measurement")
        value = states.get(out["state"], out["state"])
        return f"{attrs.get('friendly_name') or out.get('entity_id')}: {value}{(' ' + unit) if unit else ''}."
    if tool == "ha_shopping_list":
        if isinstance(out, dict) and out.get("da_comprare"):
            return tr_sys("Sulla lista della spesa: {items}.", items=", ".join(out["da_comprare"]))
        return tr_sys("La lista della spesa è vuota.") if isinstance(out, str) else None
    if tool == "ha_scene_list":
        if isinstance(out, list) and out:
            return tr_sys("Scene salvate: {names}.", names=", ".join(s["scena"] for s in out))
        return tr_sys("Nessuna scena salvata.") if isinstance(out, str) else None
    if tool == "ha_scene_apply":
        return f"{tr_sys('Fatto')}." if isinstance(out, dict) and out.get("ok") else None
    return None


# ------------------------------------------------------------------------------ the store
class Shortcuts:
    def __init__(self, hq):
        self.hq = hq
        self._lock = asyncio.Lock()

    async def enabled(self) -> bool:
        return bool(await self.hq.store.get(ENABLED_KEY, True))

    async def set_enabled(self, on: bool) -> None:
        await self.hq.store.put(ENABLED_KEY, bool(on))

    async def _data(self) -> dict:
        return await self.hq.store.get(KEY, {}) or {}

    async def listing(self) -> dict:
        data = await self._data()
        items = [
            {"key": k, "text": v["text"], "active": v["active"], "seen": v["seen"], "hits": v.get("hits", 0), "last": v.get("last")}
            for k, v in data.items()
        ]
        items.sort(key=lambda i: (not i["active"], -i["hits"], i["text"]))
        return {"enabled": await self.enabled(), "threshold": THRESHOLD, "items": items}

    async def remove(self, key: str | None) -> int:
        """One shortcut, or all of them (key None). How many went."""
        async with self._lock:
            data = await self._data()
            gone = len(data) if key is None else int(data.pop(key, None) is not None)
            await self.hq.store.put(KEY, {} if key is None else data)
            return gone

    # -------------------------------------------------------------------------- answering
    async def answer(self, text: str) -> str | None:
        """The local answer to a question learned earlier, or None (ask Claude)."""
        if ORIGIN.get() != "owner" or not await self.enabled():
            return None
        key = normalize(text)
        entry = (await self._data()).get(key)
        if not entry or not entry.get("active"):
            return None
        try:
            reply = await self._run(entry["plan"])
        except Exception as exc:
            log.info("shortcut %r failed: %s", key, exc)
            reply = None
        async with self._lock:
            data = await self._data()
            cur = data.get(key)
            if cur:
                if reply is None:
                    cur["fails"] = cur.get("fails", 0) + 1
                    if cur["fails"] >= MAX_FAILS:  # no longer works: forget the plan and learn it again
                        cur.update(active=False, seen=0, fails=0)
                else:
                    cur.update(fails=0, hits=cur.get("hits", 0) + 1, last=datetime.now(timezone.utc).isoformat())
                await self.hq.store.put(KEY, data)
        return reply

    async def _run(self, plan: list[dict]) -> str | None:
        ctx = ToolContext(self.hq, "jarvis", None)
        states = self.hq.watcher.states
        parts = []
        for step in plan:
            tool, inp = step["tool"], dict(step["input"])
            if tool not in LEARNABLE or tool not in REGISTRY:
                return None
            ids = inp.get("entity_ids") or ([inp["entity_id"]] if "entity_id" in inp else [])
            if any(e not in states for e in ids):  # renamed or gone: ask Claude
                return None
            if tool == "ha_history":
                inp["hours"] = hours_for(step.get("period", 24), self.hq.now())
            out = await REGISTRY[tool].handler(ctx, inp)
            if isinstance(out, dict) and "errore" in out:
                return None
            said = phrase(tool, out, step, self.hq)
            if said is None:
                return None
            parts.append(said)
        return "\n".join(parts) or None

    # -------------------------------------------------------------------------- learning
    async def observe(self, text: str, calls: list[tuple[str, dict, bool, str]]) -> None:
        """Called after the quick route answered `text` with these tool calls (name, input, error, output)."""
        if ORIGIN.get() != "owner" or not await self.enabled():
            return
        plan = plan_of(text, calls)
        if plan is None:
            return
        key = normalize(text)
        async with self._lock:
            data = await self._data()
            entry = data.get(key)
            if entry and entry["plan"] == plan:
                entry["seen"] += 1
                if entry["seen"] >= THRESHOLD:
                    entry["active"] = True
            else:  # new, or Claude chose differently this time: start counting again
                data[key] = {"text": re.sub(r"^\s*\[[^\]]*\]\s*", "", text).strip()[:160], "plan": plan, "seen": 1,
                             "active": False, "hits": 0, "fails": 0, "last": None}
            if len(data) > MAX_ENTRIES:  # drop what is still learning, oldest first
                for k in [k for k, v in data.items() if not v["active"]][: len(data) - MAX_ENTRIES]:
                    del data[k]
            await self.hq.store.put(KEY, data)
