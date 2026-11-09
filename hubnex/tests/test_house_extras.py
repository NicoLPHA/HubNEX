"""History (read only), light scenes kept by HubNEX, and the shopping list."""

import json
from types import SimpleNamespace

import httpx
import pytest

from hubnex.context import ORIGIN
from hubnex.integrations.homeassistant import HomeAssistant
from hubnex.tools import REGISTRY, ToolContext
from hubnex.tools.house_extras import summarize


def st(state, **attrs):
    return {"state": state, "attributes": attrs}


def house(make_hq, history=None, todo=None):
    hq = make_hq([])
    hq.watcher.states = {
        "light.woonkamer": st("on", friendly_name="Woonkamer", brightness=120, color_mode="color_temp", color_temp_kelvin=2700),
        "light.keuken": st("off", friendly_name="Keuken"),
        "light.gang": st("on", friendly_name="Gang", brightness=255, color_mode="rgb", rgb_color=[255, 100, 0]),
        "lock.voordeur": st("locked"),
        "binary_sensor.achterdeur": st("off", friendly_name="Achterdeur"),
        "sensor.temp": st("21", friendly_name="Temp", unit_of_measurement="°C"),
        "todo.shopping_list": st("2", friendly_name="Boodschappen"),
    }
    calls, added = [], []
    todo_items = list(todo or [])

    async def call_service(domain, service, data=None, by_owner=False):
        calls.append((domain, service, data))
        if (domain, service) == ("todo", "add_item"):
            added.append(data["item"])
        return []

    async def todo_items_(entity_id, status="needs_action"):
        return [{"summary": s, "status": "needs_action"} for s in todo_items]

    async def hist(ids, hours):
        return {e: (history or {}).get(e, []) for e in ids}

    hq.ha = SimpleNamespace(enabled=True, call_service=call_service, todo_items=todo_items_, history=hist)
    return hq, ToolContext(hq, "jarvis", None), calls, added


async def run(tool_name, ctx, **inp):
    return await REGISTRY[tool_name].handler(ctx, inp)


# ------------------------------------------------------------------ history
def test_measurement_summary_has_min_max_average():
    out = summarize([("t1", "19.5"), ("t2", "22"), ("t3", "21")], "°C")
    assert out["tipo"] == "misura" and out["minimo"]["valore"] == 19.5 and out["massimo"]["alle"] == "t2"
    assert out["media"] == 20.83 and out["ora"] == 21.0


def test_state_summary_counts_how_often_it_became_a_state():
    series = [("t0", "off"), ("t1", "on"), ("t2", "off"), ("t3", "on"), ("t4", "unavailable"), ("t5", "on")]
    out = summarize(series)
    assert out["tipo"] == "stati" and out["volte_in_stato"]["on"] == 3 and out["ora"] == "on"


def test_empty_history_says_so():
    assert "nota" in summarize([])


async def test_history_tool_limits_and_names(make_hq):
    hist = {"binary_sensor.achterdeur": [("a", "off"), ("b", "on"), ("c", "off"), ("d", "on")]}
    hq, ctx, *_ = house(make_hq, history=hist)
    seen = {}
    real = hq.ha.history

    async def spy(ids, hours):
        seen["ids"], seen["hours"] = ids, hours
        return await real(ids, hours)

    hq.ha.history = spy
    out = await run("ha_history", ctx, entity_ids=["binary_sensor.achterdeur"] + [f"sensor.x{i}" for i in range(9)], hours=9999)
    assert len(seen["ids"]) == 5 and seen["hours"] == 168
    door = out["entità"]["binary_sensor.achterdeur"]
    assert door["naam"] == "Achterdeur" and door["volte_in_stato"]["on"] == 2
    bad = await run("ha_history", ctx, entity_ids=["../etc/passwd", "geen entiteit"])
    assert "errore" in bad


async def test_history_client_is_a_plain_get():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        return httpx.Response(200, json=[[{"entity_id": "sensor.temp", "state": "20", "last_changed": "t"}]])

    ha = HomeAssistant("http://ha:8123", "tok")
    ha._client = httpx.AsyncClient(base_url="http://ha:8123/api", transport=httpx.MockTransport(handler))
    assert (await ha.history(["sensor.temp"], 6))["sensor.temp"] == [("t", "20")] and seen["method"] == "GET"


# ------------------------------------------------------------------ scenes
async def test_scene_saves_all_lights_and_replays_them(make_hq):
    hq, ctx, calls, _ = house(make_hq)
    out = await run("ha_scene_save", ctx, name="Serie Film")
    assert out["apparecchi"] == 3 and out["ok"]
    assert [s["scena"] for s in await run("ha_scene_list", ctx)] == ["Serie Film"]
    res = await run("ha_scene_apply", ctx, name="serie  film")  # case and spaces do not matter
    assert res["ok"] and res["apparecchi_cambiati"] == 3
    by = {d["entity_id"]: (s, d) for _, s, d in calls}
    assert by["light.keuken"][0] == "turn_off"
    assert by["light.woonkamer"][1] == {"entity_id": "light.woonkamer", "brightness": 120, "color_temp_kelvin": 2700}
    assert by["light.gang"][1]["rgb_color"] == [255, 100, 0] and "color_temp_kelvin" not in by["light.gang"][1]


async def test_scene_only_takes_lights_and_plugs(make_hq):
    hq, ctx, calls, _ = house(make_hq)
    out = await run("ha_scene_save", ctx, name="x", entities=["light.keuken", "lock.voordeur", "nietbestaand.x"])
    assert out["apparecchi"] == 1 and set(out["scartate"]) == {"lock.voordeur", "nietbestaand.x"}
    # a stored scene that names a lock is never replayed
    scenes = await hq.store.get("jarvis_scenes")
    scenes["x"]["entities"]["lock.voordeur"] = {"state": "off"}
    await hq.store.put("jarvis_scenes", scenes)
    res = await run("ha_scene_apply", ctx, name="x")
    assert res["apparecchi_cambiati"] == 1 and all(d != "lock" for d, _, _ in calls)


async def test_scene_unknown_and_delete(make_hq):
    hq, ctx, *_ = house(make_hq)
    assert "errore" in await run("ha_scene_apply", ctx, name="bestaat niet")
    await run("ha_scene_save", ctx, name="a")
    assert (await run("ha_scene_delete", ctx, name="a"))["ok"] and await run("ha_scene_list", ctx) == "Nessuna scena salvata."


@pytest.mark.parametrize("tool,inp", [
    ("ha_scene_save", {"name": "a"}), ("ha_scene_apply", {"name": "a"}), ("ha_scene_delete", {"name": "a"}),
    ("ha_shopping_add", {"items": ["melk"]}),
])
async def test_routines_cannot_change_anything(make_hq, tool, inp):  # noqa
    hq, ctx, calls, _ = house(make_hq)
    token = ORIGIN.set("routine")
    try:
        with pytest.raises(PermissionError):
            await run(tool, ctx, **inp)
    finally:
        ORIGIN.reset(token)
    assert calls == []


# ------------------------------------------------------------------ shopping list
async def test_shopping_adds_new_items_and_skips_those_already_on_the_list(make_hq):
    hq, ctx, calls, added = house(make_hq, todo=["Melk", "Eieren"])
    out = await run("ha_shopping_add", ctx, items=["melk", "Brood", "brood", "  ", "Kaas"])
    assert added == ["Brood", "Kaas"] and out["già_presenti"] == ["melk"] and out["lista"] == "todo.shopping_list"
    assert all(c[:2] == ("todo", "add_item") and c[2]["entity_id"] == "todo.shopping_list" for c in calls)
    assert (await run("ha_shopping_list", ctx))["da_comprare"] == ["Melk", "Eieren"]


async def test_shopping_list_choice(make_hq):
    hq, ctx, _, added = house(make_hq)
    del hq.watcher.states["todo.shopping_list"]
    assert "Lista" in (await run("ha_shopping_add", ctx, items=["x"]))["errore"]  # none at all
    hq.watcher.states.update({"todo.a": st("0"), "todo.b": st("0")})
    assert "disponibili" in await run("ha_shopping_add", ctx, items=["x"])  # ambiguous: ask which
    assert added == []
    out = await run("ha_shopping_add", ctx, items=["x"], list="todo.b")
    assert out["lista"] == "todo.b" and added == ["x"]
    assert "errore" in await run("ha_shopping_add", ctx, items=["x"], list="light.keuken")


async def test_todo_client_asks_for_a_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"], seen["query"], seen["body"] = request.url.path, request.url.query.decode(), json.loads(request.content)
        return httpx.Response(200, json={"changed_states": [], "service_response": {"todo.shopping_list": {"items": [{"summary": "Melk"}]}}})

    ha = HomeAssistant("http://ha:8123", "tok")
    ha._client = httpx.AsyncClient(base_url="http://ha:8123/api", transport=httpx.MockTransport(handler))
    assert await ha.todo_items("todo.shopping_list") == [{"summary": "Melk"}]
    assert seen["path"] == "/api/services/todo/get_items" and "return_response" in seen["query"]
    assert seen["body"] == {"entity_id": "todo.shopping_list", "status": "needs_action"}
