"""The calendar tool: Home Assistant's calendars (Google…) read-only, several calendars, an allow list."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx

from hubnex.integrations.homeassistant import HomeAssistant
from hubnex.tools import REGISTRY, ToolContext


def st(name):
    return {"state": "off", "attributes": {"friendly_name": name}, "last_changed": datetime.now(timezone.utc).isoformat()}


EVENTS = {
    "calendar.nico": [
        {"start": "2026-11-12T09:00:00+01:00", "end": "2026-11-12T10:00:00+01:00", "summary": "Tandarts", "location": "Den Haag"},
        {"start": "2026-11-10", "end": "2026-11-11", "summary": "Vrij", "description": "x " * 400},
    ],
    "calendar.danielle": [
        {"start": "2026-11-11T18:30:00+01:00", "end": "2026-11-11T20:00:00+01:00", "summary": "Yoga"},
    ],
}


def house(make_hq, allowed=None):
    hq = make_hq([])
    hq.watcher.states = {
        "calendar.nico": st("Nico"),
        "calendar.danielle": st("Danielle"),
        "calendar.feestdagen": st("Feestdagen"),
        "light.keuken": st("Keuken"),
    }
    hq.settings.calendar_entities = set(allowed or [])
    asked = []

    async def calendar_events(entity_ids, start, end):
        asked.append((list(entity_ids), start, end))
        return {e: EVENTS.get(e, []) for e in entity_ids}

    hq.ha = SimpleNamespace(enabled=True, calendar_events=calendar_events)
    return hq, asked, ToolContext(hq, "jarvis", None)


async def run(ctx, **inp):
    return await REGISTRY["calendar_events"].handler(ctx, inp)


async def test_client_asks_home_assistant_for_the_events_with_a_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"], seen["query"], seen["body"] = request.url.path, request.url.query.decode(), json.loads(request.content)
        return httpx.Response(200, json={"changed_states": [], "service_response": {"calendar.nico": {"events": [{"summary": "A"}]}}})

    ha = HomeAssistant("http://ha:8123", "tok")
    ha._client = httpx.AsyncClient(base_url="http://ha:8123/api", transport=httpx.MockTransport(handler))
    start, end = datetime(2026, 11, 9, tzinfo=timezone.utc), datetime(2026, 11, 16, tzinfo=timezone.utc)
    out = await ha.calendar_events(["calendar.nico"], start, end)
    assert seen["path"] == "/api/services/calendar/get_events" and "return_response" in seen["query"]
    assert seen["body"] == {"entity_id": ["calendar.nico"], "start_date_time": start.isoformat(), "end_date_time": end.isoformat()}
    assert out == {"calendar.nico": [{"summary": "A"}]}


async def test_all_calendars_are_merged_in_time_order_with_their_names(make_hq):
    hq, asked, ctx = house(make_hq)
    out = await run(ctx, **{"from": "2026-11-09", "days": 14})
    assert asked[0][0] == ["calendar.danielle", "calendar.feestdagen", "calendar.nico"]
    assert [(e["agenda"], e["titolo"]) for e in out["eventi"]] == [("Nico", "Vrij"), ("Danielle", "Yoga"), ("Nico", "Tandarts")]
    assert out["eventi"][2]["luogo"] == "Den Haag" and out["giorni"] == 14 and out["dal"] == "2026-11-09"


async def test_one_calendar_can_be_asked_for(make_hq):
    hq, asked, ctx = house(make_hq)
    out = await run(ctx, calendars=["calendar.danielle"], **{"from": "2026-11-09"})
    assert asked[0][0] == ["calendar.danielle"] and [e["titolo"] for e in out["eventi"]] == ["Yoga"]


async def test_the_allow_list_decides_which_calendars_exist_for_the_assistant(make_hq):
    hq, asked, ctx = house(make_hq, allowed={"calendar.nico", "calendar.danielle"})
    await run(ctx, **{"from": "2026-11-09"})
    assert asked[0][0] == ["calendar.danielle", "calendar.nico"], "the holiday calendar is not allowed"
    out = await run(ctx, calendars=["calendar.feestdagen"])
    assert "errore" in out and set(out["disponibili"]) == {"calendar.nico", "calendar.danielle"}
    assert len(asked) == 1, "a refused calendar is never asked for"


async def test_texts_are_clipped_and_the_period_is_limited(make_hq):
    hq, asked, ctx = house(make_hq)
    out = await run(ctx, calendars=["calendar.nico"], days=999, **{"from": "2026-11-09"})
    assert out["giorni"] == 31
    assert (asked[0][2] - asked[0][1]).days == 31
    assert all(len(e["note"]) <= 300 for e in out["eventi"])


async def test_errors_are_plain_answers_not_crashes(make_hq):
    hq, asked, ctx = house(make_hq)
    assert "errore" in await run(ctx, **{"from": "morgen"})
    hq.watcher.states = {"light.keuken": st("Keuken")}
    assert "errore" in await run(ctx)  # Home Assistant has no calendar
    hq, asked, ctx = house(make_hq)
    hq.ha.calendar_events = lambda *a, **k: _empty()
    assert "Nessun appuntamento" in await run(ctx, calendars=["calendar.nico"])


async def _empty():
    return {"calendar.nico": []}


def test_the_allow_list_option_is_read(monkeypatch):
    from hubnex.config import Settings

    monkeypatch.setenv("HUBNEX_CALENDARS", "calendar.nico, calendar.danielle; sensor.evil ,")
    assert Settings.from_env().calendar_entities == {"calendar.nico", "calendar.danielle"}
    monkeypatch.delenv("HUBNEX_CALENDARS")
    assert Settings.from_env().calendar_entities == set()
