"""Learned shortcuts: a question that keeps coming back is answered locally, never anything risky."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from hubnex.context import ORIGIN
from hubnex.i18n import set_system_lang, system_lang
from hubnex.shortcuts import THRESHOLD, hours_for, normalize, period_of, plan_of
from tests.conftest import response, text_block, tool_block

Q = "Hoe vaak is het licht in de keuken vandaag aangegaan?"
HIST = [("2026-11-09T05:00:00+00:00", "off"), ("2026-11-09T06:10:00+00:00", "on"), ("2026-11-09T07:00:00+00:00", "off"),
        ("2026-11-09T11:00:00+00:00", "on")]


@pytest.fixture(autouse=True)
def dutch():
    before = system_lang()
    set_system_lang("nl")
    yield
    set_system_lang(before)


def history_call(ids=("light.keuken",), hours=None, error=False, out='{"ore": 5}'):
    inp = {"entity_ids": list(ids)}
    if hours is not None:
        inp["hours"] = hours
    return ("ha_history", inp, error, out)


def house(make_hq, responses=None):
    hq = make_hq(responses or [])
    hq.watcher.states = {
        "light.keuken": {"entity_id": "light.keuken", "state": "off", "attributes": {"friendly_name": "Keuken"}},
        "sensor.temp": {"entity_id": "sensor.temp", "state": "21", "attributes": {"friendly_name": "Woonkamer", "unit_of_measurement": "°C"}},
    }
    seen = []

    async def history(ids, hours):
        seen.append((list(ids), hours))
        return {"light.keuken": HIST, "sensor.temp": [("2026-11-09T05:00:00+00:00", "19.5"), ("2026-11-09T09:00:00+00:00", "22"), ("2026-11-09T11:00:00+00:00", "21")]}

    async def conversation(text, agent_id="x", language=None):
        return {"response": {"response_type": "error"}}

    hq.ha = SimpleNamespace(enabled=True, history=history, conversation=conversation)
    hq.org.boss_tools.append("ha_history")
    return hq, seen


# ------------------------------------------------------------------ what is a question, what is a plan
def test_normalize_ignores_case_and_punctuation_but_keeps_the_room_note():
    assert normalize("Hoe vaak, is het LICHT aan?!") == normalize("hoe vaak is het licht aan")
    assert normalize("[Sono nella stanza Keuken] is het licht aan?") != normalize("[Sono nella stanza Gang] is het licht aan?")


def test_periods_are_recomputed():
    assert period_of(Q) == "today" and period_of("hoe warm was het het afgelopen uur") == 1
    assert period_of("hoe vaak ging de deur open deze week") == 168 and period_of("hoe vaak ging de deur open") is None
    assert period_of("hoe vaak ging de deur gisteren open") is False
    noon = datetime(2026, 11, 9, 14, 20, tzinfo=timezone.utc)
    assert hours_for("today", noon) == 15 and hours_for(168, noon) == 168


def test_plan_keeps_read_only_calls_and_skips_discovery():
    discovery = ("ha_list_entities", {"search": "keuken"}, False, "[]")
    plan = plan_of(Q, [discovery, history_call()])
    assert plan == [{"tool": "ha_history", "input": {"entity_ids": ["light.keuken"]}, "period": "today"}]
    assert plan_of("hoe vaak ging de deur open", [history_call(["binary_sensor.d"])])[0]["period"] == 24


@pytest.mark.parametrize("text,calls", [
    (Q, [("ha_call_service", {"domain": "light", "service": "turn_on"}, False, "")]),  # an action: never
    (Q, [("ha_call_service", {"domain": "lock", "service": "unlock"}, False, "")]),
    (Q, [history_call(), ("ha_call_service", {"domain": "light"}, False, "")]),  # one risky call spoils the plan
    (Q, [history_call(error=True)]),
    (Q, [history_call(out='{"errore": "x"}')]),
    ("En in de gang?", [history_call()]),  # a follow-up means nothing alone
    ("Hoe vaak ging die deur open vandaag", [history_call()]),
    ("hoe vaak ging de deur open", [history_call(hours=72)]),  # 72 hours that the question does not explain
    ("hoe vaak ging de deur gisteren open", [history_call()]),
    ("licht?", [history_call()]),  # too short to be a question of its own
    (Q, []),
])
def test_plan_refuses(text, calls):
    assert plan_of(text, calls) is None


# ------------------------------------------------------------------ learning and answering
async def test_learns_after_three_identical_answers_and_answers_locally(make_hq):
    hq, seen = house(make_hq)
    sc = hq.shortcuts
    assert await sc.answer(Q) is None
    for n in range(1, THRESHOLD):
        await sc.observe(Q, [history_call()])
        assert (await sc.listing())["items"][0]["active"] is False and await sc.answer(Q) is None
    await sc.observe(Q, [history_call()])
    assert (await sc.listing())["items"][0]["active"] is True
    reply = await sc.answer(Q.upper())  # capitals do not matter
    # the first row is the state at the start of the period: it is not counted as "turned off"
    assert reply == "Keuken: 2 keer aan, 1 keer uit (vandaag); nu aan."
    assert seen[-1][1] >= 1 and hq.client.requests == []
    assert (await sc.listing())["items"][0]["hits"] == 1


async def test_another_plan_starts_counting_again(make_hq):
    hq, _ = house(make_hq)
    for _ in range(2):
        await hq.shortcuts.observe(Q, [history_call()])
    await hq.shortcuts.observe(Q, [history_call(["light.keuken", "sensor.temp"])])
    item = (await hq.shortcuts.listing())["items"][0]
    assert item["seen"] == 1 and item["active"] is False


async def test_measurements_are_phrased_with_decimal_commas(make_hq):
    hq, _ = house(make_hq)
    q = "Wat was de temperatuur in de woonkamer vandaag?"
    for _ in range(THRESHOLD):
        await hq.shortcuts.observe(q, [history_call(["sensor.temp"])])
    reply = await hq.shortcuts.answer(q)
    assert "nu 21 °C" in reply and "laagste 19,5 °C" in reply and "hoogste 22 °C" in reply and "gemiddeld 20,8 °C" in reply


async def test_an_entity_that_is_gone_falls_back_and_a_dead_shortcut_is_dropped(make_hq):
    hq, _ = house(make_hq)
    for _ in range(THRESHOLD):
        await hq.shortcuts.observe(Q, [history_call()])
    del hq.watcher.states["light.keuken"]
    for _ in range(3):
        assert await hq.shortcuts.answer(Q) is None
    item = (await hq.shortcuts.listing())["items"][0]
    assert item["active"] is False and item["seen"] == 0  # forgotten: learned again from scratch


async def test_switch_off_remove_and_routines(make_hq):
    hq, _ = house(make_hq)
    sc = hq.shortcuts
    for _ in range(THRESHOLD):
        await sc.observe(Q, [history_call()])
    await sc.set_enabled(False)
    assert await sc.answer(Q) is None
    await sc.observe(Q, [history_call()])  # not learning while off
    await sc.set_enabled(True)
    assert await sc.answer(Q) is not None
    token = ORIGIN.set("routine")
    try:  # only the owner's questions teach or use shortcuts
        assert await sc.answer(Q) is None
        await sc.observe("hoe vaak ging de deur open vandaag", [history_call(["light.keuken"])])
    finally:
        ORIGIN.reset(token)
    assert len((await sc.listing())["items"]) == 1
    assert await sc.remove(normalize(Q)) == 1 and (await sc.listing())["items"] == []


async def test_a_stored_plan_is_never_trusted_with_another_tool(make_hq):
    hq, _ = house(make_hq)
    await hq.store.put("shortcuts", {normalize(Q): {
        "text": Q, "seen": 9, "active": True, "hits": 0, "fails": 0, "last": None,
        "plan": [{"tool": "ha_call_service", "input": {"domain": "lock", "service": "unlock"}}]}})
    assert await hq.shortcuts.answer(Q) is None


# ------------------------------------------------------------------ in the conversation
async def test_the_quick_route_teaches_and_the_fourth_time_needs_no_claude(make_hq):
    turns = []
    for i in range(THRESHOLD):
        turns += [response([tool_block("ha_history", {"entity_ids": ["light.keuken"]}, f"t{i}")], "tool_use"),
                  response([text_block("Twee keer, meneer.")], "end_turn")]
    hq, seen = house(make_hq, turns)
    for _ in range(THRESHOLD):
        reply, _, by = await hq.converse("dashboard", Q, quick=True, local=True)
        assert by == "quick" and reply == "Twee keer, meneer."
    before = len(hq.client.requests)
    reply, _, by = await hq.converse("dashboard", Q, quick=True, local=True)
    assert by == "learned" and reply.startswith("Keuken: 2 keer aan") and len(hq.client.requests) == before
    # what the answer was is in the chat history like any other
    assert [h["text"] for h in await hq.store.chat_history("dashboard", 2)][0] == Q


async def test_sensitive_questions_never_use_a_shortcut(make_hq):
    hq, _ = house(make_hq, [response([text_block("Mag ik bevestiging, meneer?")], "end_turn")])
    q = "ontgrendel de voordeur vandaag"
    await hq.store.put("shortcuts", {normalize(q): {
        "text": q, "seen": 9, "active": True, "hits": 0, "fails": 0, "last": None,
        "plan": [{"tool": "ha_history", "input": {"entity_ids": ["light.keuken"]}, "period": "today"}]}})
    _, _, by = await hq.converse("dashboard", q, quick=True, local=True)
    assert by == "jarvis"
