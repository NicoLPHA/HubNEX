"""House view: Home Assistant areas and entities on the floor plan, live, editable from the dashboard."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from hubnex.casa import LayoutError, parse_layout
from hubnex.integrations.ha_ws import HAWatcher, websocket_url
from hubnex.main import create_app

AREAS = [{"area_id": "sala", "name": "Sala da Pranzo"}, {"area_id": "soggiorno", "name": "Soggiorno"},
         {"area_id": "giardino", "name": "Giardino"}, {"area_id": "garage", "name": "Parcheggio"}]
DEVICES = [{"id": "dev-lampadario", "area_id": "sala"}]
ENTITIES = [
    {"entity_id": "light.lampadario", "device_id": "dev-lampadario", "area_id": None},  # area from its device
    {"entity_id": "light.lampada", "device_id": None, "area_id": "soggiorno"},
    {"entity_id": "sensor.lampada_rssi", "device_id": None, "area_id": "soggiorno", "entity_category": "diagnostic"},
    {"entity_id": "switch.vecchia", "device_id": None, "area_id": "soggiorno", "disabled_by": "user"},
    {"entity_id": "switch.irrigazione", "device_id": None, "area_id": "giardino"},
    {"entity_id": "light.angolo", "device_id": None, "area_id": None},
]


def st(eid, state, **attrs):
    return {"entity_id": eid, "state": state, "attributes": attrs}


STATES = [
    st("light.lampadario", "on", friendly_name="Lampadario", brightness=153),
    st("light.lampada", "off", friendly_name="Lampada da terra"),
    st("sensor.lampada_rssi", "-60"),
    st("switch.irrigazione", "off", friendly_name="Irrigazione"),
    st("light.angolo", "off", friendly_name="Lampada angolo"),
    st("scene.cinema", "unknown", friendly_name="Cinema"),
    st("alarm_control_panel.casa", "armed_away", friendly_name="Allarme"),  # no area
    st("binary_sensor.no_unique_id", "off", friendly_name="Vecchio sensore"),
]

LAYOUT = """
floors:
  - name: Piano terra
    aspect: 1.06
    rooms:
      - { area: Balcone, x: 0, y: 0, w: 97.8, h: 85.8, outline: true }
      - { area: sala da pranzo, x: 48.6, y: 41.1, w: 38.2, h: 23 }
      - { area: Soggiorno, x: 44.1, y: 66.6, w: 31.2, h: 31.4 }
outside: [Giardino]
"""


class FakeWS:
    """A Home Assistant WebSocket: answers commands, can push events."""

    def __init__(self):
        self.sent = []
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.inbox.put_nowait({"type": "auth_required"})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def recv(self):
        return json.dumps(await self.inbox.get())

    def __aiter__(self):
        return self

    async def __anext__(self):
        msg = await self.inbox.get()
        if msg is None:
            raise StopAsyncIteration
        return json.dumps(msg)

    async def send(self, raw):
        msg = json.loads(raw)
        self.sent.append(msg)
        t = msg["type"]
        if t == "auth":
            self.inbox.put_nowait({"type": "auth_ok"} if msg["access_token"] == "tok" else {"type": "auth_invalid"})
            return
        result = {
            "config/area_registry/list": AREAS,
            "config/floor_registry/list": [],
            "config/device_registry/list": DEVICES,
            "config/entity_registry/list": ENTITIES,
            "get_states": STATES,
        }.get(t)
        if t == "config/entity_registry/update":
            result = {"entity_entry": {"entity_id": msg["entity_id"], "area_id": msg["area_id"], "device_id": None}}
        self.inbox.put_nowait({"id": msg["id"], "type": "result", "success": True, "result": result})

    def push(self, event_type, data):
        self.inbox.put_nowait({"type": "event", "event": {"event_type": event_type, "data": data}})


async def connected(events=None):
    ws = FakeWS()

    async def on_event(kind, eid, state):
        if events is not None:
            events.append((kind, eid, state and state["state"]))

    w = HAWatcher("http://supervisor/core", "tok", on_event, connect=lambda url: ws)
    task = asyncio.create_task(w.run())
    await asyncio.wait_for(w.ready.wait(), 2)
    return w, ws, task


def test_websocket_url():
    assert websocket_url("http://supervisor/core") == "ws://supervisor/core/websocket"
    assert websocket_url("https://casa.example:8123/") == "wss://casa.example:8123/api/websocket"


async def test_watcher_loads_registries_and_follows_changes():
    events = []
    w, ws, task = await connected(events)
    assert ws.sent[0] == {"type": "auth", "access_token": "tok"}
    assert {"type": "subscribe_events", "event_type": "state_changed"} == {k: v for k, v in ws.sent[1].items() if k != "id"}
    assert w.area_of("light.lampadario") == "sala"  # inherited from the device
    assert w.area_of("light.lampada") == "soggiorno"
    ws.push("state_changed", {"entity_id": "light.lampada", "new_state": st("light.lampada", "on")})
    await asyncio.sleep(0.05)
    assert w.states["light.lampada"]["state"] == "on"
    assert ("state", "light.lampada", "on") in events
    await w.set_area("light.angolo", "soggiorno")
    assert ws.sent[-1]["type"] == "config/entity_registry/update" and ws.sent[-1]["area_id"] == "soggiorno"
    assert w.area_of("light.angolo") == "soggiorno"
    task.cancel()


async def test_rooms_follow_areas_with_the_owners_adjustments(make_hq):
    hq = make_hq([])
    w, ws, task = await connected()
    hq.casa.ha = hq.watcher = w
    hq.casa.save_layout(LAYOUT)
    view = hq.casa.build()
    areas = {a["id"]: a for a in view["areas"]}
    assert areas["sala"]["entities"] == ["light.lampadario"]
    assert areas["soggiorno"]["entities"] == ["light.lampada"]  # no diagnostic, no disabled
    assert areas["giardino"]["outside"] and areas["garage"]["placed"] is False  # not drawn: shown below the plan
    rooms = view["floors"][0]["rooms"]
    assert [r["area_id"] for r in rooms] == [None, "sala", "soggiorno"]  # Balcone is not an HA area: drawn only
    assert view["scenes"] == ["scene.cinema"]
    assert view["alarms"] == ["alarm_control_panel.casa"] and view["states"]["alarm_control_panel.casa"]["s"] == "armed_away"
    assert view["states"]["light.lampadario"] == {"s": "on", "n": "Lampadario", "k": "light", "a": {"brightness": 153}}

    await hq.casa.show_here("soggiorno", "binary_sensor.no_unique_id")  # dashboard only
    await hq.casa.hide("sala", "light.lampadario")
    areas = {a["id"]: a for a in hq.casa.build()["areas"]}
    assert areas["soggiorno"]["entities"] == ["binary_sensor.no_unique_id", "light.lampada"]
    assert areas["sala"]["entities"] == []
    assert [c["entity_id"] for c in hq.casa.candidates("angolo", "soggiorno")] == ["light.angolo"]
    task.cancel()


def test_layout_is_checked_before_saving(tmp_path):
    assert parse_layout(LAYOUT)["floors"][0]["rooms"][0]["outline"] is True
    with pytest.raises(LayoutError, match="fuori dal disegno"):
        parse_layout("floors: [{rooms: [{area: X, x: 90, y: 0, w: 20, h: 10}]}]")
    with pytest.raises(LayoutError, match="serve 'area'"):
        parse_layout("floors: [{rooms: [{x: 0, y: 0, w: 20, h: 10}]}]")
    with pytest.raises(LayoutError, match="YAML"):
        parse_layout("floors: [")


def test_dashboard_api(settings, make_hq):
    hq = make_hq([])
    calls = []

    class FakeREST:
        enabled = True

        async def call_service(self, domain, service, data, by_owner=False):
            calls.append((domain, service, data, by_owner))
            return []

        async def close(self):
            pass

    hq.ha = FakeREST()
    with TestClient(create_app(settings, hq=hq, start_workers=False)) as client:
        w, ws, task = client.portal.call(connected)
        hq.casa.ha = hq.watcher = w

        r = client.put("/api/casa/layout", json={"text": "floors: ["})
        assert r.status_code == 422
        assert client.post("/api/casa/layout", json={"text": LAYOUT}).json() == {"ok": True}
        assert "Soggiorno" in client.get("/api/casa/layout").json()["text"]

        view = client.get("/api/casa").json()
        assert view["floors"][0]["rooms"][1]["name"] == "Sala da Pranzo"

        # Unlocking is blocked for Jarvis, not for the owner pressing the button.
        client.post("/api/casa/call", json={"domain": "lock", "service": "unlock", "data": {"entity_id": "lock.porta"}})
        assert calls == [("lock", "unlock", {"entity_id": "lock.porta"}, True)]

        assert client.post("/api/casa/rooms/soggiorno/entities", json={"entity_id": "light.angolo", "mode": "ha"}).json()["ok"]
        assert ws.sent[-1]["type"] == "config/entity_registry/update"
        r = client.post("/api/casa/rooms/soggiorno/entities", json={"entity_id": "binary_sensor.no_unique_id", "mode": "ha"})
        assert r.status_code == 409 and "solo alla plancia" in r.json()["detail"]
        client.post("/api/casa/rooms/soggiorno/entities", json={"entity_id": "binary_sensor.no_unique_id", "mode": "local"})
        client.post("/api/casa/rooms/soggiorno/entities/light.lampada/remove")
        soggiorno = next(a for a in client.get("/api/casa").json()["areas"] if a["id"] == "soggiorno")
        assert soggiorno["entities"] == ["binary_sensor.no_unique_id", "light.angolo"]
        client.portal.call(lambda: task.cancel())


async def test_live_changes_reach_the_dashboard(make_hq):
    hq = make_hq([])
    events = hq.subscribe()
    w, ws, task = await connected()
    hq.watcher = hq.casa.ha = w
    w.on_event = hq._ha_event
    hq.casa.build()
    ws.push("state_changed", {"entity_id": "light.lampada", "new_state": st("light.lampada", "on", friendly_name="Lampada da terra")})
    ws.push("state_changed", {"entity_id": "sensor.lampada_rssi", "new_state": st("sensor.lampada_rssi", "-61")})  # not shown
    ws.push("area_registry_updated", {})
    await asyncio.sleep(1.3)
    got = []
    while not events.empty():
        got.append(events.get_nowait())
    assert {"type": "ha", "e": "light.lampada", "v": {"s": "on", "n": "Lampada da terra", "k": "light", "a": {}}} in got
    assert not any(e.get("e") == "sensor.lampada_rssi" for e in got)
    assert {"type": "casa_changed"} in got
    task.cancel()


def test_layout_mistakes_are_explained_and_hand_edits_picked_up(make_hq, tmp_path):
    with pytest.raises(LayoutError, match="chiave sconosciuta: plan"):
        parse_layout("plan:\n  - {area: X, x: 0, y: 0, w: 10, h: 10}")
    with pytest.raises(LayoutError, match="nessun piano"):
        parse_layout("outside: [Giardino]")
    # Italian keys and a single floor without "floors:" are fine.
    assert parse_layout("piani:\n  - nome: Terra\n    stanze:\n      - {area: X, x: 0, y: 0, w: 10, h: 10}")["floors"][0]["name"] == "Terra"
    assert parse_layout("rooms:\n  - {area: X, x: 0, y: 0, w: 10, h: 10}")["floors"][0]["rooms"][0]["area"] == "X"

    hq = make_hq([])
    assert hq.casa.build()["floors"] == []
    hq.casa.path.write_text(LAYOUT)  # written with File editor, no restart
    assert len(hq.casa.build()["floors"]) == 1
    hq.casa.path.write_text("floors: [")
    import os
    os.utime(hq.casa.path, (1, 1))
    view = hq.casa.build()
    assert "YAML" in view["layout_error"]


def test_owner_picks_the_rooms_temperature_sensor(settings, make_hq):
    hq = make_hq([])
    with TestClient(create_app(settings, hq=hq, start_workers=False)) as client:
        w, ws, task = client.portal.call(connected)
        hq.casa.ha = hq.watcher = w
        assert client.post("/api/casa/rooms/sala/temperature", json={"entity_id": "sensor.temp_sala"}).json()["ok"]
        sala = next(a for a in client.get("/api/casa").json()["areas"] if a["id"] == "sala")
        assert sala["temp"] == "sensor.temp_sala"
        client.post("/api/casa/rooms/sala/temperature", json={"entity_id": None})
        assert next(a for a in client.get("/api/casa").json()["areas"] if a["id"] == "sala")["temp"] is None
        assert client.post("/api/casa/rooms/nessuna/temperature", json={}).status_code == 404
        client.portal.call(lambda: task.cancel())


def test_entities_can_be_shown_as_another_kind(settings, make_hq):
    hq = make_hq([])
    with TestClient(create_app(settings, hq=hq, start_workers=False)) as client:
        w, ws, task = client.portal.call(connected)
        hq.casa.ha = hq.watcher = w
        assert client.post("/api/casa/entities/switch.irrigazione/kind", json={"kind": "light"}).json()["ok"]
        view = client.get("/api/casa").json()
        assert view["states"]["switch.irrigazione"]["k"] == "light" and view["states"]["switch.irrigazione"]["nk"] == "switch"
        assert client.post("/api/casa/entities/switch.irrigazione/kind", json={"kind": "razzo"}).status_code == 422
        client.post("/api/casa/entities/light.lampadario/kind", json={"kind": "siren"})
        assert client.get("/api/casa").json()["states"]["light.lampadario"]["k"] == "siren"
        client.post("/api/casa/entities/switch.irrigazione/kind", json={"kind": None})
        assert "nk" not in client.get("/api/casa").json()["states"]["switch.irrigazione"]
        client.portal.call(lambda: task.cancel())


def test_camera_frames_come_through_the_addon(settings, make_hq):
    hq = make_hq([])

    class FakeREST:
        enabled = True

        async def camera_image(self, eid):
            return b"\xff\xd8jpeg", "image/jpeg"

        async def camera_stream(self, eid):
            async def chunks():
                yield b"--f\r\n"
                yield b"frame"
            return "multipart/x-mixed-replace; boundary=f", chunks()

        async def close(self):
            pass

    hq.ha = FakeREST()
    with TestClient(create_app(settings, hq=hq, start_workers=False)) as client:
        w, ws, task = client.portal.call(connected)
        hq.casa.ha = hq.watcher = w
        r = client.get("/api/casa/camera/camera.ingresso?t=1")
        assert r.content == b"\xff\xd8jpeg" and r.headers["content-type"] == "image/jpeg"
        assert client.get("/api/casa/camera/light.lampadario").status_code == 404
        r = client.get("/api/casa/camera/camera.ingresso/stream")
        assert r.headers["content-type"].startswith("multipart/x-mixed-replace") and r.content == b"--f\r\nframe"
        client.portal.call(lambda: task.cancel())
