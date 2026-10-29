"""Runs agents' routines (every N minutes / daily at HH:MM) and warns about deadlines."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import date, datetime, timedelta

from hubnex.config import Routine
from hubnex.hq import HQ

log = logging.getLogger("hubnex.scheduler")

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
TICK_SECONDS = 30
DEADLINE_WARNING = timedelta(hours=24)


def parse_interval(value: str) -> int:
    """'30m' -> 1800, '6h' -> 21600, '1d' -> 86400, '45s' -> 45."""
    m = re.fullmatch(r"\s*(\d+)\s*([smhd])\s*", value)
    if not m:
        raise ValueError(f"intervallo non valido: {value!r} (usa es. 30m, 6h, 1d)")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]


def is_due_at(routine: Routine, now: datetime, last_run_day: date | None) -> bool:
    """Daily routine: due once the clock passes `at` on an allowed day, once per day."""
    if routine.days and DAYS[now.weekday()] not in [d.lower()[:3] for d in routine.days]:
        return False
    hh, mm = (int(x) for x in routine.at.split(":"))
    return (now.hour, now.minute) >= (hh, mm) and last_run_day != now.date()


def parse_due(due: str, tz) -> datetime:
    dt = datetime.fromisoformat(due)
    if len(due) <= 10:  # date only: treat as 9:00 that day
        dt = dt.replace(hour=9)
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


class Scheduler:
    def __init__(self, hq: HQ):
        self.hq = hq
        self._last_every: dict[tuple[str, int], float] = {}
        self._last_at: dict[tuple[str, int], date] = {}
        now = hq.now()
        start = time.monotonic()
        for spec in hq.org.agents:
            for i, r in enumerate(spec.routines):
                if not r.enabled:
                    continue
                if r.every:
                    parse_interval(r.every)  # fail fast on bad config
                    self._last_every[(spec.id, i)] = start
                if r.at and is_due_at(r, now, None):
                    # Already past today's slot at startup: don't fire it retroactively.
                    self._last_at[(spec.id, i)] = now.date()

    async def run(self) -> None:
        log.info("Scheduler avviato")
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("scheduler tick failed")
            await asyncio.sleep(TICK_SECONDS)

    async def tick(self) -> None:
        now = self.hq.now()
        mono = time.monotonic()
        for spec in self.hq.org.agents:
            for i, r in enumerate(spec.routines):
                key = (spec.id, i)
                if not r.enabled:
                    continue
                if r.every and mono - self._last_every[key] >= parse_interval(r.every):
                    self._last_every[key] = mono
                    self._fire(spec.id, r)
                elif r.at and is_due_at(r, now, self._last_at.get(key)):
                    self._last_at[key] = now.date()
                    self._fire(spec.id, r)
        await self.check_deadlines(now)

    def _fire(self, agent_id: str, routine: Routine) -> None:
        log.info("routine %s: %s", agent_id, routine.task[:60])
        # Routines speak up with notify_owner only when there is something worth saying.
        self.hq.run_agent_background(agent_id, routine.task, source="routine", report=False)

    async def check_deadlines(self, now: datetime) -> None:
        for d in await self.hq.store.deadlines():
            if d["notified"]:
                continue
            try:
                due = parse_due(d["due"], self.hq.tz)
            except ValueError:
                continue
            if due - now <= DEADLINE_WARNING:
                when = "è SCADUTA" if due < now else f"scade il {due:%d/%m alle %H:%M}"
                await self.hq.notify(f"⏰ Scadenza: *{d['title']}* {when}." + (f"\n{d['notes']}" if d["notes"] else ""))
                await self.hq.store.deadline_mark_notified(d["id"])
