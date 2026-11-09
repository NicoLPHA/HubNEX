"""Smart notifications about the house, without Claude: fixed rules checked on Home Assistant's
live states. They only warn; a button on the notification (pressed by the owner) is the only
way they change anything.

Channels: the Home Assistant companion app (push, with buttons), the Telegram group, Home
Assistant's own notifications. A rule warns once per episode; the notification goes away by
itself when the problem is solved.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from hubnex.i18n import system_lang, tr_sys

if TYPE_CHECKING:
    from hubnex.hq import HQ

log = logging.getLogger("hubnex.alerts")

TICK = 20  # seconds between checks
COOLDOWN = timedelta(minutes=30)  # a problem solved and back within this time doesn't warn again
RULES = ("safety", "windows", "away", "power", "night", "battery", "offline", "stock")
SAFETY = {"moisture", "smoke", "gas", "carbon_monoxide", "safety"}
RAIN = {"rainy", "pouring", "lightning-rainy", "snowy-rainy", "hail"}
OFFLINE_DOMAINS = {"light", "switch", "climate", "lock", "cover", "binary_sensor", "sensor", "fan", "valve", "alarm_control_panel", "camera"}
MAX_LISTED = 8

DEFAULTS: dict[str, Any] = {
    "quiet": {"from": "", "to": ""},  # "" = no quiet hours
    "phones": None,  # None = every phone with the Home Assistant app
    "exclude": [],  # entities never checked
    "rules": {
        "safety": {"on": True, "app": True, "telegram": True, "ha": True},
        "windows": {"on": True, "app": True, "telegram": True, "ha": False, "minutes": 5},
        "away": {"on": True, "app": True, "telegram": True, "ha": False, "minutes": 5},
        "power": {"on": True, "app": True, "telegram": True, "ha": False, "minutes": 10, "watts": 3000},
        "night": {"on": True, "app": True, "telegram": True, "ha": False, "minutes": 15, "at": "23:30", "until": "06:00"},
        "battery": {"on": True, "app": True, "telegram": False, "ha": True, "percent": 15},
        "offline": {"on": True, "app": True, "telegram": False, "ha": True, "minutes": 60},
        "stock": {"on": True, "app": True, "telegram": True, "ha": False},
    },
}
NUMBERS = {"minutes": (0, 1440), "watts": (100, 100000), "percent": (1, 99)}
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def clean_config(raw: dict | None) -> dict:
    raw = raw or {}
    out: dict[str, Any] = {"rules": {}}
    q = raw.get("quiet") or {}
    out["quiet"] = {k: q.get(k) if isinstance(q.get(k), str) and HHMM.match(q.get(k)) else "" for k in ("from", "to")}
    phones = raw.get("phones")
    out["phones"] = [p for p in phones if isinstance(p, str) and p.startswith("mobile_app_")] if isinstance(phones, list) else None
    out["exclude"] = sorted({e for e in raw.get("exclude") or [] if isinstance(e, str) and "." in e})
    for rule, base in DEFAULTS["rules"].items():
        got = (raw.get("rules") or {}).get(rule) or {}
        r = dict(base)
        for k, v in base.items():
            if k not in got:
                continue
            if isinstance(v, bool):
                r[k] = bool(got[k])
            elif k in NUMBERS:
                try:
                    lo, hi = NUMBERS[k]
                    r[k] = max(lo, min(hi, int(float(got[k]))))
                except (TypeError, ValueError):
                    pass
            elif k in ("at", "until") and isinstance(got[k], str) and HHMM.match(got[k]):
                r[k] = got[k]
        out["rules"][rule] = r
    return out


def in_window(now: datetime, start: str, end: str) -> bool:
    """`now` between HH:MM `start` and `end`, across midnight too. Empty = never."""
    if not start or not end or start == end:
        return False
    t = now.strftime("%H:%M")
    return start <= t < end if start < end else t >= start or t < end


def _float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _since(state: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(state.get("last_changed")).replace("Z", "+00:00"))
    except ValueError:
        return None


def listing(names: list[str]) -> str:
    names = sorted(names)
    if len(names) > MAX_LISTED:
        return ", ".join(names[:MAX_LISTED]) + " " + tr_sys("e altri {n}", n=len(names) - MAX_LISTED)
    return ", ".join(names)


@dataclass
class Finding:
    key: str
    rule: str
    title: str
    text: str
    items: dict[str, datetime | None]  # item -> since when it is a problem (None = from now)
    actions: list[tuple[str, list[tuple[str, str, dict]]]] = field(default_factory=list)  # (label, [(domain, service, data)])
    urgent: bool = False


@dataclass
class Episode:
    finding: Finding
    first_seen: dict[str, datetime]
    sent_items: set[str] = field(default_factory=set)
    sent_at: datetime | None = None
    telegram: tuple[int, int] | None = None
    tokens: list[str] = field(default_factory=list)


class Alerts:
    def __init__(self, hq: "HQ"):
        self.hq = hq
        self.cfg = clean_config(None)
        self.episodes: dict[str, Episode] = {}
        self.cleared: dict[str, datetime] = {}
        self.pending: dict[str, tuple[str, list[tuple[str, str, dict]]]] = {}
        self.phones: list[dict] = []
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        self.cfg = clean_config(await self.hq.store.get("alerts_cfg"))

    async def save(self, raw: dict) -> dict:
        self.cfg = clean_config(raw)
        await self.hq.store.put("alerts_cfg", self.cfg)
        await self.tick()
        return self.cfg

    # ------------------------------------------------------------------ helpers
    @property
    def ha(self):
        return self.hq.watcher

    def name(self, eid: str) -> str:
        return (self.hq.casa.compact(eid) or {}).get("n") or eid

    def device_name(self, eid: str) -> str:
        """Which device it is, and where: "Sensore porta (Ingresso)". The entity's own name
        ("Batteria") alone says nothing."""
        reg = self.ha.entities.get(eid) or {}
        dev = self.ha.devices.get(reg.get("device_id") or "")
        name = ((dev.get("name_by_user") or dev.get("name")) if dev else None) or self.name(eid)
        area = (self.ha.areas.get(self.ha.area_of(eid) or "") or {}).get("name")
        return f"{name} ({area})" if area and area.lower() not in name.lower() else name

    def _watched(self, eid: str) -> bool:
        return eid not in self.cfg["exclude"] and self.hq.casa.visible(eid)

    def _dc(self, eid: str) -> str | None:
        return ((self.ha.states.get(eid) or {}).get("attributes") or {}).get("device_class")

    def candidates(self, rule: str) -> list[str]:
        """The entities a rule looks at (exclusions included), for the settings popup."""
        st = self.ha.states
        visible = self.hq.casa.visible
        if rule == "safety":
            return sorted(e for e in st if e.startswith("binary_sensor.") and self._dc(e) in SAFETY and visible(e))
        if rule == "windows":
            return sorted(e for e in st if e.startswith("binary_sensor.") and self._dc(e) == "window" and visible(e))
        if rule == "away":
            return sorted(
                e for e in st if visible(e) and (
                    (e.startswith("binary_sensor.") and self._dc(e) in ("door", "garage_door", "opening"))
                    or (e.startswith("cover.") and self._dc(e) in ("garage", "gate", "door"))
                    or e.startswith("lock.")
                )
            )
        if rule == "power":
            p = self.hq.casa.energy_config().get("power")
            return [p] if p else []
        if rule == "night":
            return sorted(e for e in st if e.startswith("light.") and visible(e))
        if rule == "battery":
            return sorted(e for e in st if self._dc(e) == "battery" and e.split(".")[0] in ("sensor", "binary_sensor") and visible(e))
        if rule == "offline":
            return sorted(e for e in st if e.split(".")[0] in OFFLINE_DOMAINS and visible(e))
        if rule == "stock":
            return self.hq.casa.stocks()
        return []

    def _on(self, rule: str) -> list[str]:
        return [e for e in self.candidates(rule) if e not in self.cfg["exclude"]]

    # ------------------------------------------------------------------ the rules
    def findings(self, now: datetime) -> list[Finding]:
        st = self.ha.states
        rules = self.cfg["rules"]
        out: list[Finding] = []
        state = lambda e: (st.get(e) or {}).get("state")  # noqa: E731

        if rules["safety"]["on"]:
            labels = {
                "moisture": tr_sys("Perdita d'acqua"), "smoke": tr_sys("Fumo"), "gas": tr_sys("Gas"),
                "carbon_monoxide": tr_sys("Monossido di carbonio"), "safety": tr_sys("Allarme di sicurezza"),
            }
            for e in self._on("safety"):
                if state(e) == "on":
                    what = labels.get(self._dc(e) or "", labels["safety"])
                    out.append(Finding(f"safety:{e}", "safety", what, f"{what}: {self.device_name(e)}", {e: None}, urgent=True))

        if rules["windows"]["on"]:
            open_ = [e for e in self._on("windows") if state(e) == "on"]
            climates = [s for e, s in st.items() if e.startswith("climate.") and self.hq.casa.visible(e)]
            heating = any((s.get("attributes") or {}).get("hvac_action") == "heating" or (
                "hvac_action" not in (s.get("attributes") or {}) and s.get("state") == "heat") for s in climates)
            cooling = any((s.get("attributes") or {}).get("hvac_action") == "cooling" or (
                "hvac_action" not in (s.get("attributes") or {}) and s.get("state") == "cool") for s in climates)
            raining = any(s.get("state") in RAIN for e, s in st.items() if e.startswith("weather."))
            if open_ and (heating or cooling or raining):
                why = [w for w, on in ((tr_sys("il riscaldamento è acceso"), heating), (tr_sys("il condizionatore è acceso"), cooling), (tr_sys("sta piovendo"), raining)) if on]
                names = listing([self.name(e) for e in open_])
                out.append(Finding("windows", "windows", tr_sys("Finestre aperte"),
                                   tr_sys("Aperte: {names}. Intanto {why}.", names=names, why=tr_sys(" e ").join(why)),
                                   {e: None for e in open_}))

        if rules["away"]["on"]:
            people = [s for e, s in st.items() if e.startswith("person.")]
            known = all(p.get("state") not in ("unknown", "unavailable", None) for p in people)  # not while HA restarts
            if people and known and all(p.get("state") != "home" for p in people):
                problem = {}
                close: list[tuple[str, str, dict]] = []
                for e in self._on("away"):
                    s = state(e)
                    if e.startswith("lock.") and s in ("unlocked", "open"):
                        problem[e] = None
                        close.append(("lock", "lock", {"entity_id": e}))
                    elif e.startswith("cover.") and s in ("open", "opening"):
                        problem[e] = None
                        close.append(("cover", "close_cover", {"entity_id": e}))
                    elif e.startswith("binary_sensor.") and s == "on":
                        problem[e] = None
                if problem:
                    out.append(Finding("away", "away", tr_sys("Casa vuota, qualcosa è aperto"),
                                       tr_sys("Non c'è nessuno in casa e sono aperti: {names}.", names=listing([self.name(e) for e in problem])),
                                       problem, [(tr_sys("Chiudi"), close)] if close else []))

        if rules["power"]["on"]:
            for e in self._on("power"):
                s = st.get(e) or {}
                v = _float(s.get("state"))
                if v is None:
                    continue
                unit = (s.get("attributes") or {}).get("unit_of_measurement") or "W"
                watts = v * 1000 if unit.lower() == "kw" else v
                if watts >= rules["power"]["watts"]:
                    kw = f"{watts / 1000:.1f}"
                    kw = kw.replace(".", ",") if system_lang() in ("it", "nl") else kw
                    out.append(Finding("power", "power", tr_sys("Consumo alto"),
                                       tr_sys("La casa sta usando {kw} kW da più di {m} minuti.", kw=kw, m=rules["power"]["minutes"]),
                                       {e: None}))

        if rules["night"]["on"] and in_window(now, rules["night"]["at"], rules["night"]["until"]):
            lit = [e for e in self._on("night") if state(e) == "on"]
            if lit:
                out.append(Finding("night", "night", tr_sys("Luci accese di notte"),
                                   tr_sys("Sono ancora accese: {names}.", names=listing([self.name(e) for e in lit])),
                                   {e: None for e in lit},
                                   [(tr_sys("Spegni"), [("light", "turn_off", {"entity_id": lit})])]))

        if rules["battery"]["on"]:
            low = {}
            for e in self._on("battery"):
                s = st.get(e) or {}
                if e.startswith("binary_sensor."):
                    if s.get("state") == "on":
                        low[e] = self.device_name(e)
                else:
                    v = _float(s.get("state"))
                    if v is not None and v < rules["battery"]["percent"]:
                        low[e] = f"{self.device_name(e)} {v:.0f}%"
            if low:
                out.append(Finding("battery", "battery", tr_sys("Batterie scariche"),
                                   tr_sys("Da cambiare: {names}.", names=listing(list(low.values()))), {e: None for e in low}))

        if rules["offline"]["on"]:
            limit = timedelta(minutes=rules["offline"]["minutes"])
            gone: dict[str, datetime | None] = {}
            labels: dict[str, str] = {}
            for e in self._on("offline"):
                s = st.get(e) or {}
                if s.get("state") != "unavailable":
                    continue
                since = _since(s)
                if since and now - since < limit:
                    continue
                dev = self.ha.devices.get((self.ha.entities.get(e) or {}).get("device_id") or "")
                item = f"device:{dev['id']}" if dev else e
                gone[item] = since
                labels[item] = self.device_name(e)
            if gone:
                out.append(Finding("offline", "offline", tr_sys("Dispositivi non raggiungibili"),
                                   tr_sys("Non rispondono da più di {m} minuti: {names}.", m=rules["offline"]["minutes"], names=listing(list(labels.values()))),
                                   gone))
        if rules["stock"]["on"]:
            for e in self._on("stock"):
                s = st.get(e) or {}
                v = _float(s.get("state"))
                low = self.hq.casa.stock_of(e)["low"]
                if v is not None and v <= low:
                    unit = (s.get("attributes") or {}).get("unit_of_measurement") or ""
                    left = f"{v:.0f} {unit}".strip()
                    out.append(Finding(f"stock:{e}", "stock", tr_sys("Scorta da riordinare"),
                                       tr_sys("{name}: ne restano {left}, sotto la soglia di {low}. È ora di ordinare.", name=self.name(e), left=left, low=low),
                                       {e: None}))
        return out

    # ------------------------------------------------------------------ the engine
    def _delay(self, f: Finding) -> timedelta:
        if f.urgent or f.rule == "offline":  # offline already waited, on Home Assistant's clock
            return timedelta(0)
        if f.rule == "battery":
            return timedelta(minutes=30)  # a reading hovering around the threshold doesn't warn
        return timedelta(minutes=self.cfg["rules"][f.rule].get("minutes", 0))

    def _quiet(self, now: datetime) -> bool:
        return in_window(now, self.cfg["quiet"]["from"], self.cfg["quiet"]["to"])

    async def tick(self) -> None:
        async with self._lock:
            now = self.hq.now()
            seen = set()
            for f in self.findings(now):
                seen.add(f.key)
                ep = self.episodes.get(f.key)
                if ep is None:
                    ep = self.episodes[f.key] = Episode(f, {})
                ep.finding = f
                for item in f.items:
                    ep.first_seen.setdefault(item, now)
                for item in list(ep.first_seen):  # an item that came back later starts again
                    if item not in f.items:
                        del ep.first_seen[item]
                ready = {i for i in f.items if now - ep.first_seen[i] >= self._delay(f)}
                if not ready - ep.sent_items:
                    continue
                if ep.sent_at is None and f.key in self.cleared and now - self.cleared[f.key] < COOLDOWN:
                    continue
                if not f.urgent and self._quiet(now):
                    continue  # waits for the end of the quiet hours, if still there
                ep.sent_items |= ready
                await self._send(ep, now)
            for key in [k for k in self.episodes if k not in seen]:
                ep = self.episodes.pop(key)
                if ep.sent_at:
                    self.cleared[key] = now
                    await self._clear(ep)

    async def run(self) -> None:
        await self.load()
        while True:
            try:
                if self.ha.ready.is_set():
                    if not self.phones:
                        self.phones = await self.ha.phones()
                    await self.tick()
            except Exception:
                log.exception("controllo delle notifiche fallito")
            await asyncio.sleep(TICK)

    def on_state(self, eid: str, state: dict | None) -> None:
        """A safety sensor going off is checked at once, not at the next tick."""
        if state and state.get("state") == "on" and eid.startswith("binary_sensor.") and self._dc(eid) in SAFETY:
            t = asyncio.create_task(self.tick())
            self.hq._background.add(t)
            t.add_done_callback(self.hq._background.discard)

    # ------------------------------------------------------------------ channels
    def _tag(self, key: str) -> str:
        return "hubnex_" + re.sub(r"[^a-z0-9_]", "_", key.lower())

    def _phone_services(self) -> list[str]:
        known = [p["service"] for p in self.phones]
        chosen = self.cfg["phones"]
        return known if chosen is None else [p for p in chosen if p in known]

    async def _send(self, ep: Episode, now: datetime) -> None:
        f = ep.finding
        rule = self.cfg["rules"][f.rule]
        first = ep.sent_at is None
        ep.sent_at = now
        for tok in ep.tokens:
            self.pending.pop(tok, None)
        ep.tokens = []
        buttons = []
        for label, calls in f.actions[:3]:
            tok = secrets.token_hex(5)
            self.pending[tok] = (label, calls)
            ep.tokens.append(tok)
            buttons.append((label, tok))
        await self.hq.log("ha", f"{f.title}: {f.text}")
        if rule.get("app"):
            data: dict[str, Any] = {"tag": self._tag(f.key), "group": "hubnex"}
            if buttons:
                data["actions"] = [{"action": f"HUBNEX_{tok}", "title": label} for label, tok in buttons]
            if f.urgent:
                data.update({"ttl": 0, "priority": "high", "channel": "HubNEX urgente", "importance": "high",
                             "push": {"interruption-level": "time-sensitive"}})
            for service in self._phone_services():
                await self._safe(self.hq.ha.call_service("notify", service, {"title": f.title, "message": f.text, "data": data}))
        if rule.get("telegram") and self.hq.team_enabled:
            if ep.telegram and not first:  # the old message loses its buttons, the new one has them
                await self._safe(self.hq.team.set_buttons(None, *ep.telegram, None))
            kb = [[(label, f"h:{tok}") for label, tok in buttons]] if buttons else None  # h: house
            title = tr_sys("URGENTE: {title}", title=f.title) if f.urgent else f.title
            res = await self._safe(self.hq.team.post(None, f"{title}\n{f.text}", buttons=kb))
            if isinstance(res, tuple):
                ep.telegram = res
        if rule.get("ha"):
            await self._safe(self.hq.ha.call_service(
                "persistent_notification", "create", {"title": f"HubNEX · {f.title}", "message": f.text, "notification_id": self._tag(f.key)}))

    async def _clear(self, ep: Episode) -> None:
        f = ep.finding
        rule = self.cfg["rules"].get(f.rule, {})
        for tok in ep.tokens:
            self.pending.pop(tok, None)
        await self.hq.log("ha", tr_sys("Risolto: {title}", title=f.title))
        if rule.get("app"):
            for service in self._phone_services():
                await self._safe(self.hq.ha.call_service("notify", service, {"message": "clear_notification", "data": {"tag": self._tag(f.key)}}))
        if ep.telegram and self.hq.team_enabled:
            await self._safe(self.hq.team.set_buttons(None, *ep.telegram, None))
        if rule.get("ha"):
            await self._safe(self.hq.ha.call_service("persistent_notification", "dismiss", {"notification_id": self._tag(f.key)}))

    async def _safe(self, coro):
        try:
            return await coro
        except Exception as exc:
            log.warning("notifica non inviata: %s", exc)
            return None

    async def press(self, token: str) -> str | None:
        """A button on a notification, pressed by the owner: the only thing that acts."""
        got = self.pending.pop(token, None)
        if not got:
            return None
        label, calls = got
        for domain, service, data in calls:
            await self.hq.ha.call_service(domain, service, data, by_owner=True)
        names = []
        for _, _, data in calls:
            eids = data.get("entity_id")
            names += eids if isinstance(eids, list) else [eids]
        msg = tr_sys("Dalla notifica: {label} ({names})", label=label, names=listing([self.name(e) for e in names if e]))
        await self.hq.log("ha", msg)
        return msg

    async def test(self) -> list[str]:
        """A test notification on every channel in use."""
        sent = []
        title, text = "HubNEX", tr_sys("Notifica di prova: se la leggi, gli avvisi della casa arrivano qui.")
        rules = self.cfg["rules"].values()
        if any(r["on"] and r["app"] for r in rules):
            self.phones = await self.ha.phones() or self.phones
            for service in self._phone_services():
                if await self._safe(self.hq.ha.call_service("notify", service, {"title": title, "message": text, "data": {"tag": "hubnex_test"}})) is not None:
                    sent.append(next((p["name"] for p in self.phones if p["service"] == service), service))
        if any(r["on"] and r["telegram"] for r in rules) and self.hq.team_enabled:
            if await self._safe(self.hq.team.post(None, text)) is not None:
                sent.append("Telegram")
        if any(r["on"] and r["ha"] for r in rules):
            if await self._safe(self.hq.ha.call_service("persistent_notification", "create", {"title": title, "message": text, "notification_id": "hubnex_test"})) is not None:
                sent.append("Home Assistant")
        return sent

    async def overview(self) -> dict:
        if not self.phones and self.ha.ready.is_set():
            self.phones = await self.ha.phones()
        return {
            "cfg": self.cfg,
            "phones": self.phones,
            "telegram": self.hq.team_enabled,
            "watched": {r: [{"e": e, "n": self.name(e)} for e in self.candidates(r)] for r in RULES},
            "active": [
                {"key": k, "rule": ep.finding.rule, "title": ep.finding.title, "text": ep.finding.text,
                 "sent": ep.sent_at is not None, "urgent": ep.finding.urgent}
                for k, ep in self.episodes.items()
            ],
        }
