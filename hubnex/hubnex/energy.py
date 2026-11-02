"""The house's energy panel: Italian time bands (F1/F2/F3), today's power and kWh per band.

ARERA bands: F1 working days 8-19; F2 working days 7-8 and 19-23, Saturday 7-23; F3 the
rest (nights, Sundays, national holidays). The owner can instead take the band from a sensor
of their own, or have a single tariff.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from hubnex.i18n import system_lang

PANEL_VIEWS = ("reactor", "day", "bill")
DEFAULT_CONFIG: dict[str, Any] = {
    "views": list(PANEL_VIEWS),  # which of the three views the panel shows, in this order
    "band_mode": "arera",  # arera | sensor | single
    "band_sensor": None,  # mode "sensor": an entity whose state is F1/F2/F3
    "bands": {},  # {"F1": "sensor.…", "F2": …, "F3": …} kWh of the period (utility meters)
    "prices": {},  # {"F1": "input_number.…", …} €/kWh, optional
    "total": None,  # kWh of the period when there are no bands (or a total of one's own)
    "cost": None,  # € of the period, if Home Assistant computes it
    "power": None,  # W now; default: the floor plan's energy.power
    "contract_kw": 3.0,  # the meter's power, for "x% del contatore"
    "cycle": "bimonthly",  # monthly | bimonthly: the billing period, when the meters don't say
    "readouts": [],  # other entities to show (voltage, power factor, energy drawn…)
}


def easter(year: int) -> date:
    """Western Easter (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def holidays(year: int) -> set[date]:
    fixed = [(1, 1), (1, 6), (4, 25), (5, 1), (6, 2), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)]
    return {date(year, m, d) for m, d in fixed} | {easter(year) + timedelta(days=1)}


def arera_band(dt: datetime) -> str:
    d = dt.date()
    if d.weekday() == 6 or d in holidays(d.year):
        return "F3"
    h = dt.hour
    if d.weekday() == 5:
        return "F2" if 7 <= h < 23 else "F3"
    if 8 <= h < 19:
        return "F1"
    if h == 7 or 19 <= h < 23:
        return "F2"
    return "F3"


def band_until(dt: datetime) -> tuple[str, datetime]:
    """The band now and when it ends (the next hour where it changes)."""
    band = arera_band(dt)
    t = dt.replace(minute=0, second=0, microsecond=0)
    for _ in range(24 * 8):
        t += timedelta(hours=1)
        if arera_band(t) != band:
            return band, t
    return band, t


def _parse(ts: str, tz) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)
    except (ValueError, AttributeError):
        return None


def day_profile(points: list[tuple[str, str]], now: datetime, unit: str = "W", buckets: int = 96) -> dict[str, Any]:
    """Today's power from midnight: the average per quarter of an hour (W) and the kWh per
    ARERA band, integrating the sensor's steps (a value holds until the next one)."""
    tz = now.tzinfo
    midnight = datetime.combine(now.date(), time(0), tz)
    scale = 1000.0 if unit.lower() == "kw" else 1.0
    steps: list[tuple[datetime, float]] = []
    for ts, v in points:
        t = _parse(ts, tz)
        try:
            w = float(v) * scale
        except (TypeError, ValueError):
            continue
        if t is not None:
            steps.append((t, w))
    steps.sort()
    # the value at midnight is the last one before it
    before = [s for s in steps if s[0] <= midnight]
    today = [s for s in steps if s[0] > midnight]
    if before:
        today.insert(0, (midnight, before[-1][1]))
    kwh = {"F1": 0.0, "F2": 0.0, "F3": 0.0}
    span = (now - midnight).total_seconds()
    size = 86400 / buckets
    sums = [0.0] * buckets
    secs = [0.0] * buckets
    for i, (t, w) in enumerate(today):
        end = today[i + 1][0] if i + 1 < len(today) else now
        cur = max(t, midnight)
        while cur < end:
            # up to the next quarter of an hour: bands only change on the hour
            nxt = min(end, midnight + timedelta(seconds=(int((cur - midnight).total_seconds() // size) + 1) * size))
            dt = (nxt - cur).total_seconds()
            if dt <= 0:
                break
            kwh[arera_band(cur)] += w * dt / 3600 / 1000
            b = min(buckets - 1, int((cur - midnight).total_seconds() // size))
            sums[b] += w * dt
            secs[b] += dt
            cur = nxt
    profile = [[round(i * size / 60), round(sums[i] / secs[i], 1)] for i in range(buckets) if secs[i] > 0 and i * size < span]
    return {"points": profile, "kwh": {k: round(v, 3) for k, v in kwh.items()}, "now_min": round(span / 60)}


def clean_config(raw: dict) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    # The ARERA calendar is Italian: elsewhere the default is a single rate (or one's own sensor).
    cfg["band_mode"] = "arera" if system_lang() == "it" else "single"
    for key in DEFAULT_CONFIG:
        if key in raw and raw[key] is not None:
            cfg[key] = raw[key]
    cfg["views"] = [v for v in cfg["views"] if v in PANEL_VIEWS]
    if cfg["band_mode"] not in ("arera", "sensor", "single"):
        cfg["band_mode"] = "arera"
    if cfg["cycle"] not in ("monthly", "bimonthly"):
        cfg["cycle"] = "bimonthly"
    cfg["bands"] = {k: v for k, v in (cfg["bands"] or {}).items() if k in ("F1", "F2", "F3") and v}
    cfg["prices"] = {k: v for k, v in (cfg["prices"] or {}).items() if k in ("F1", "F2", "F3") and v}
    cfg["readouts"] = [r for r in cfg["readouts"] if isinstance(r, str)][:12]
    try:
        cfg["contract_kw"] = max(0.5, min(float(cfg["contract_kw"]), 100.0))
    except (TypeError, ValueError):
        cfg["contract_kw"] = 3.0
    return cfg


def entities(cfg: dict) -> list[str]:
    """Every entity the panel shows (so their changes reach the dashboard live)."""
    out = [cfg.get("band_sensor"), cfg.get("total"), cfg.get("cost"), cfg.get("power")]
    out += list(cfg.get("bands", {}).values()) + list(cfg.get("prices", {}).values()) + list(cfg.get("readouts", []))
    return [e for e in out if e]
