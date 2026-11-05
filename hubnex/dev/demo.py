"""HubNEX with a pretend Home Assistant and a pretend Claude: for trying the dashboard,
taking screenshots and the browser tests. No real house, no API key, nothing leaves the machine.

    python dev/demo.py 8765            # then open http://127.0.0.1:8765
    python dev/demo.py 8765 casa.yaml  # with your own floor plan file
    DEMO_LANG=en python dev/demo.py 8765   # an English house and an English-speaking add-on
"""
import io, math, os, re, sys, tempfile, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from PIL import Image, ImageDraw

from hubnex.config import Settings, load_org
from hubnex.hq import HQ
from hubnex.main import create_app
from hubnex.store import Store
from tests import test_casa as T
from tests.conftest import ROOT, FakeClient, _Stream, response, text_block

now = datetime.now(timezone.utc)
ago = lambda m: (now - timedelta(minutes=m)).isoformat()
names = ["Soggiorno", "Cucina", "Camera da letto", "Studio", "Bagno", "Corridoio", "Lavanderia", "Giardino"]
slug = lambda n: n.lower().replace(" ", "_")
T.AREAS[:] = [{"area_id": slug(n), "name": n} for n in names]
T.DEVICES[:] = []
T.ENTITIES[:] = []
T.STATES[:] = []


def add(eid, area, state, lc=30, device=None, **a):
    T.ENTITIES.append({"entity_id": eid, "area_id": area, "device_id": device})
    T.STATES.append({"entity_id": eid, "state": state, "attributes": a, "last_changed": ago(lc)})


add("light.faretti_tv", "soggiorno", "on", brightness=102, supported_color_modes=["brightness"], friendly_name="Faretti TV")
add("light.lampada_terra", "soggiorno", "on", brightness=255, supported_color_modes=["color_temp", "hs"], color_mode="color_temp", color_temp_kelvin=2700, min_color_temp_kelvin=2200, max_color_temp_kelvin=6500, friendly_name="Lampada da terra")
add("light.striscia", "soggiorno", "off", supported_color_modes=["hs"], friendly_name="Striscia LED")
add("climate.soggiorno", "soggiorno", "heat", friendly_name="Clima soggiorno", current_temperature=21.8, temperature=22, hvac_modes=["off", "heat", "cool", "auto"], hvac_action="heating", target_temp_step=0.5, current_humidity=46)
add("cover.salotto", "soggiorno", "open", friendly_name="Tapparella salotto", current_position=40)
add("media_player.tv", "soggiorno", "playing", friendly_name="TV Soggiorno", media_title="Interstellar", media_artist="Netflix", volume_level=0.35, supported_features=16384 | 1 | 4 | 16 | 32, media_position=4300, media_duration=10140, media_position_updated_at=ago(1))
add("switch.presa_tv", "soggiorno", "on", device="dev-tv", friendly_name="Presa TV")
add("sensor.presa_tv_potenza", None, "120", device="dev-tv", device_class="power", unit_of_measurement="W", friendly_name="Potenza TV")
add("binary_sensor.presenza_soggiorno", "soggiorno", "on", 3, device_class="occupancy", friendly_name="Presenza soggiorno")
add("lock.ingresso", "corridoio", "locked", friendly_name="Porta ingresso", code_format="^\\d{4}$")
add("lock.garage", "corridoio", "locked", friendly_name="Porta garage")
add("light.cucina", "cucina", "on", brightness=204, supported_color_modes=["brightness"], friendly_name="Soffitto cucina")
add("light.sottopensile", "cucina", "off", supported_color_modes=["onoff"], friendly_name="Sottopensile")
add("sensor.temp_cucina", "cucina", "22.1", device_class="temperature", unit_of_measurement="°C", friendly_name="Temperatura cucina")
add("sensor.umid_cucina", "cucina", "48", device_class="humidity", unit_of_measurement="%", friendly_name="Umidità cucina")
add("switch.bollitore", "cucina", "on", 40, device="dev-kettle", friendly_name="Bollitore")
add("sensor.bollitore_potenza", None, "1850", device="dev-kettle", device_class="power", unit_of_measurement="W", friendly_name="Potenza bollitore")
add("camera.cucina", "cucina", "streaming", friendly_name="Cucina", supported_features=2)
add("sensor.temp_camera", "camera_da_letto", "19.6", device_class="temperature", unit_of_measurement="°C", friendly_name="Temperatura camera")
add("binary_sensor.finestra_camera", "camera_da_letto", "on", 35, device_class="window", friendly_name="Finestra camera")
add("light.comodini", "camera_da_letto", "off", supported_color_modes=["brightness"], friendly_name="Comodini")
add("sensor.temp_studio", "studio", "20.9", device_class="temperature", unit_of_measurement="°C", friendly_name="Temperatura studio")
add("light.yeelight", "studio", "on", brightness=200, supported_color_modes=["hs"], rgb_color=[123, 92, 255], friendly_name="Yeelight")
add("sensor.umid_bagno", "bagno", "71", device_class="humidity", unit_of_measurement="%", friendly_name="Umidità bagno")
add("switch.lavatrice", "lavanderia", "on", device="dev-lav", friendly_name="Lavatrice")
add("sensor.lavatrice_potenza", None, "1920", device="dev-lav", device_class="power", unit_of_measurement="W", friendly_name="Potenza lavatrice")
add("binary_sensor.allagamento", "lavanderia", "off", 600, device_class="moisture", friendly_name="Allagamento")
add("valve.irrigazione", "giardino", "open", 12, friendly_name="Irrigazione", supported_features=3)
add("camera.ingresso", "giardino", "idle", friendly_name="Ingresso", supported_features=2)
add("person.marco", None, "home", 300, friendly_name="Marco")
add("person.sara", None, "home", 90, friendly_name="Sara")
add("person.luca", None, "Scuola", 200, friendly_name="Luca", battery_level=64)
add("alarm_control_panel.casa", None, "armed_night", friendly_name="Allarme casa", supported_features=1 | 2 | 4, code_format="number")
add("scene.buonanotte", None, "scening", friendly_name="Buonanotte")
add("scene.cinema", None, "scening", friendly_name="Cinema")
add("scene.esco", None, "scening", friendly_name="Esco")
add("scene.rientro", None, "scening", friendly_name="Rientro")
add("sensor.potenza_casa", None, "1840", device_class="power", unit_of_measurement="W", friendly_name="Potenza casa")
add("sensor.energia_oggi", None, "9.6", device_class="energy", unit_of_measurement="kWh", friendly_name="Energia oggi")
add("weather.casa", None, "sunny", temperature=14, friendly_name="Meteo")
add("input_datetime.stufa_accensione", None, "06:30:00", has_date=False, has_time=True, friendly_name="Stufa accensione")
add("input_datetime.stufa_spegnimento", None, "22:00:00", has_date=False, has_time=True, friendly_name="Stufa spegnimento")
add("input_number.stufa_potenza", "soggiorno", "3", min=1, max=5, step=1, mode="slider", friendly_name="Potenza stufa")
add("binary_sensor.corridoio_movimento", "corridoio", "off", 25, device_class="motion", friendly_name="Corridoio")
add("binary_sensor.corridoio_occupazione", "corridoio", "on", 2, device_class="occupancy", friendly_name="Corridoio Occupazione")
add("sensor.corridoio_lux", "corridoio", "37", device_class="illuminance", unit_of_measurement="lx", friendly_name="Corridoio Illuminamento")
add("sensor.energia_f1", None, "52.66", device_class="energy", unit_of_measurement="kWh", friendly_name="Fascia F1", last_period="102.4", last_reset="2026-09-01T00:00:00+02:00", meter_period="bimonthly")
add("sensor.energia_f2", None, "89.44", device_class="energy", unit_of_measurement="kWh", friendly_name="Fascia F2", last_period="92.0", last_reset="2026-09-01T00:00:00+02:00", meter_period="bimonthly")
add("sensor.energia_f3", None, "52.15", device_class="energy", unit_of_measurement="kWh", friendly_name="Fascia F3", last_period="133.0", last_reset="2026-09-01T00:00:00+02:00", meter_period="bimonthly")
add("sensor.spesa_bimestre", None, "100.61", unit_of_measurement="€", friendly_name="Totale bimestrale")
add("sensor.tensione", None, "242.9", device_class="voltage", unit_of_measurement="V", friendly_name="Tensione")
add("sensor.fattore_potenza", None, "-0.75", device_class="power_factor", friendly_name="Fattore di potenza")
add("sensor.energia_prelevata", None, "7426.14", device_class="energy", unit_of_measurement="kWh", friendly_name="Energia prelevata")
add("input_boolean.stufa_automatica", None, "on", friendly_name="Stufa automatica")
add("input_boolean.stufa_weekend", None, "off", friendly_name="Stufa weekend")
add("input_boolean.stufa_notte", None, "on", friendly_name="Stufa notte")
add("input_select.stufa_modo", "soggiorno", "Comfort", options=["Eco", "Comfort", "Notte"], friendly_name="Modalità stufa")
# a robot vacuum and its map (an image entity of the same device, as Roborock does)
T.DEVICES.append({"id": "dev-robot", "name": "Robot aspirapolvere", "area_id": "corridoio"})
add("vacuum.robot", None, "cleaning", 12, device="dev-robot", friendly_name="Robot aspirapolvere", battery_level=64,
    fan_speed="Bilanciata", fan_speed_list=["Silenziosa", "Bilanciata", "Turbo", "Max"], status="Pulisce il soggiorno",
    supported_features=8192 | 4 | 16 | 32 | 512)
add("image.robot_mappa", None, "2026-11-05T07:00:00+00:00", device="dev-robot", friendly_name="Mappa robot")
# the entrance camera with what it detects
add("binary_sensor.ingresso_veicolo", "giardino", "on", 1, device_class="moving", friendly_name="Ingresso Veicolo in movimento")
add("binary_sensor.ingresso_persona", "giardino", "off", 47, device_class="occupancy", friendly_name="Ingresso Persona")
# music in the kitchen, with everything a music player has
add("media_player.cucina", "cucina", "playing", friendly_name="Altoparlante cucina", media_title="Clair de Lune", media_artist="Claude Debussy",
    media_album_name="Suite bergamasque", app_name="Spotify", volume_level=0.42, is_volume_muted=False, shuffle=True, repeat="all",
    source="Spotify", source_list=["Spotify", "Radio", "Bluetooth", "TV"], media_position=95, media_duration=301, media_position_updated_at=ago(0),
    supported_features=1 | 4 | 8 | 16 | 32 | 2048 | 16384 | 32768 | 262144)

EN = os.environ.get("DEMO_LANG") == "en"
NAMES_EN = {
    "Soggiorno": "Living room", "Cucina": "Kitchen", "Camera da letto": "Bedroom", "Studio": "Study",
    "Bagno": "Bathroom", "Corridoio": "Hallway", "Lavanderia": "Laundry", "Giardino": "Garden",
    "Piano terra": "Ground floor", "Allagamento": "Flood", "Allarme casa": "House alarm",
    "Bollitore": "Kettle", "Buonanotte": "Good night", "Cinema": "Movie", "Clima soggiorno": "Living room climate",
    "Comodini": "Bedside lamps", "Corridoio Illuminamento": "Hallway illuminance",
    "Corridoio Occupazione": "Hallway occupancy", "Energia oggi": "Energy today",
    "Energia prelevata": "Energy drawn", "Esco": "Going out", "Faretti TV": "TV spotlights",
    "Fascia F1": "Band F1", "Fascia F2": "Band F2", "Fascia F3": "Band F3", "Fattore di potenza": "Power factor",
    "Finestra camera": "Bedroom window", "Ingresso": "Entrance", "Irrigazione": "Irrigation",
    "Lampada da terra": "Floor lamp", "Lavatrice": "Washing machine", "Meteo": "Weather",
    "Modalità stufa": "Stove mode", "Porta garage": "Garage door", "Porta ingresso": "Front door",
    "Potenza TV": "TV power", "Potenza bollitore": "Kettle power", "Potenza casa": "House power",
    "Potenza lavatrice": "Washing machine power", "Potenza stufa": "Stove power", "Presa TV": "TV plug",
    "Presenza soggiorno": "Living room presence", "Rientro": "Coming home", "Soffitto cucina": "Kitchen ceiling",
    "Sottopensile": "Under-cabinet", "Striscia LED": "LED strip", "Stufa accensione": "Stove on",
    "Stufa automatica": "Stove automatic", "Stufa notte": "Stove night", "Stufa spegnimento": "Stove off",
    "Stufa weekend": "Stove weekend", "TV Soggiorno": "Living room TV", "Tapparella salotto": "Living room blind",
    "Temperatura camera": "Bedroom temperature", "Temperatura cucina": "Kitchen temperature",
    "Temperatura studio": "Study temperature", "Tensione": "Voltage", "Totale bimestrale": "Period total",
    "Umidità bagno": "Bathroom humidity", "Umidità cucina": "Kitchen humidity", "Notte": "Night",
}
if EN:  # the same house, in English
    for a in T.AREAS:
        a["name"] = NAMES_EN.get(a["name"], a["name"])
    for st in T.STATES:
        at = st["attributes"]
        at["friendly_name"] = NAMES_EN.get(at.get("friendly_name"), at.get("friendly_name"))
        if "options" in at:
            at["options"] = [NAMES_EN.get(o, o) for o in at["options"]]

d = tempfile.mkdtemp()
layout = sys.argv[2] if len(sys.argv) > 2 else None
LAYOUT = """floors:
  - name: Piano terra
    aspect: 1.3
    rooms:
      - { area: Soggiorno, x: 0, y: 0, w: 42, h: 50 }
      - { area: Cucina, x: 42, y: 0, w: 30, h: 50 }
      - { area: Studio, x: 72, y: 0, w: 28, h: 50 }
      - { area: Camera da letto, x: 0, y: 50, w: 36, h: 50 }
      - { area: Corridoio, x: 36, y: 50, w: 22, h: 50 }
      - { area: Bagno, x: 58, y: 50, w: 20, h: 50 }
      - { area: Lavanderia, x: 78, y: 50, w: 22, h: 50 }
outside: [Giardino]
energy: { power: sensor.potenza_casa, today: sensor.energia_oggi }
"""
if EN:
    for it, en in sorted(NAMES_EN.items(), key=lambda x: -len(x[0])):
        LAYOUT = LAYOUT.replace(it, en)
open(d + "/casa.yaml", "w").write(open(layout).read() if layout else LAYOUT)
s = Settings(db_path=d + "/t.db", agents_file=str(ROOT / "config" / ("agents.en.yaml" if EN else "agents.yaml")), language="en" if EN else "it", casa_file=d + "/casa.yaml", ha_url="http://supervisor/core", ha_token="tok")


class DemoClaude(FakeClient):
    """Claude stand-in: one polite sentence, whatever is asked."""

    def _stream(self, **kwargs):
        self.requests.append(kwargs)
        return _Stream(response([text_block("Sono la demo di HubNEX: qui Claude non c'è, ma la casa risponde.")], "end_turn"))


s.monthly_budget_usd = 15.0
hq = HQ(s, load_org(s.agents_file), Store(s.db_path), client=DemoClaude([]))
hq.watcher._connect = lambda url: T.FakeWS()


def seed_costs() -> None:
    """Six weeks of Claude spend, so the spend popup has something to show."""
    import random
    from hubnex.hq import BOSS_ID
    rnd = random.Random(7)
    agents = [a.id for a in hq.org.agents][:4]
    for back in range(42):
        day = (datetime.now() - timedelta(days=back)).strftime("%Y-%m-%d")
        busy = 0.4 if (datetime.now() - timedelta(days=back)).weekday() >= 5 else 1.0
        rows = [(BOSS_ID, "claude-sonnet-5-5", 0.25), (BOSS_ID, "claude-haiku-5-5", 0.03), ("mail", "claude-haiku-5-5", 0.04)]
        rows += [(a, "claude-sonnet-5-5", 0.08) for a in agents if a != "mail"]
        for agent, model, base in rows:
            cost = base * busy * (0.3 + 1.4 * rnd.random())
            calls = max(1, int(cost * 60))
            hq.store._conn.execute(
                "INSERT INTO usage_daily VALUES (?,?,?,?,?,?,?)",
                (day, agent, model, calls, calls * 9000, calls * 400, cost),
            )
    hq.store._conn.commit()


seed_costs()


def seed_cards() -> None:
    """A composed card: the entrance camera with what it detects."""
    import json
    card = {"id": "c1", "name": "Ingresso", "entities": ["camera.ingresso", "binary_sensor.ingresso_veicolo", "binary_sensor.ingresso_persona"], "size": "wide"}
    adjust = {"extra": {}, "hidden": {}, "cards": {"giardino": [card]}}
    hq.store._conn.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", ("casa_adjust", json.dumps(adjust)))
    hq.store._conn.commit()


seed_cards()


async def demo_phones():
    return [{"service": "mobile_app_pixel_9", "name": "Pixel 9"}, {"service": "mobile_app_ipad", "name": "iPad"}]


hq.watcher.phones = demo_phones


class REST:
    enabled = True
    blocked = set()

    async def close(self):
        pass

    async def call_service(self, domain, service, data, by_owner=False):
        eid = data.get("entity_id")
        if isinstance(eid, str) and eid in hq.watcher.states:
            st = dict(hq.watcher.states[eid])
            if service in ("set_datetime", "set_value", "select_option"):
                st["state"] = data.get("time") or data.get("date") or data.get("datetime") or str(data.get("value", data.get("option")))
                hq.watcher.states[eid] = st
                await hq._ha_event("state", eid, st)
                return []
            if domain == "light" and service == "turn_on" and any(k in data for k in ("brightness_pct", "color_temp_kelvin", "rgb_color")):
                a = dict(st.get("attributes") or {})
                if "brightness_pct" in data:
                    a["brightness"] = round(data["brightness_pct"] * 2.55)
                if "color_temp_kelvin" in data:
                    a.update(color_temp_kelvin=data["color_temp_kelvin"], color_mode="color_temp")
                    a.pop("rgb_color", None)
                if "rgb_color" in data:
                    a.update(rgb_color=list(data["rgb_color"]), color_mode="hs")
                st.update(state="on", attributes=a, last_changed=datetime.now(timezone.utc).isoformat())
                hq.watcher.states[eid] = st
                await hq._ha_event("state", eid, st)
                return []
            flip = {"toggle": None, "turn_on": "on", "turn_off": "off", "open_valve": "open", "close_valve": "closed", "unlock": "unlocked", "lock": "locked"}
            if service in flip:
                st["state"] = flip[service] or ("off" if st["state"] == "on" else "on")
                st["last_changed"] = datetime.now(timezone.utc).isoformat()
                hq.watcher.states[eid] = st
                await hq._ha_event("state", eid, st)
        return []

    async def history(self, eids, hours=24):
        out = {}
        if eids == ["sensor.potenza_casa"]:
            import random
            random.seed(3)
            day = now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
            pts = []
            t = day - timedelta(hours=1)
            while t < now:
                h = t.astimezone().hour + t.astimezone().minute / 60
                w = 180 + 60 * random.random()
                if 6.8 < h < 8: w += 900
                if 12 < h < 13.2: w += 1900
                if 19 < h < 21.5: w += 1200 + 300 * random.random()
                pts.append((t.isoformat(), str(round(w))))
                t += timedelta(minutes=10)
            return {"sensor.potenza_casa": pts}
        for i, e in enumerate(eids):
            base = float(hq.watcher.states[e]["state"])
            out[e] = [((now - timedelta(minutes=30 * k)).isoformat(), str(round(base + math.sin(k / 4 + i) * base * 0.06, 2))) for k in range(48, -1, -1)]
        return out

    async def conversation(self, text, agent_id=None):
        """Home Assistant's own sentences, in short: "accendi/spegni <nome>"."""
        m = re.match(r"\s*(accendi|spegni)\s+(?:la |il |lo |l'|le |i )?(.+?)\s*$", text, re.I)
        if m:
            want = m.group(2).lower()
            for eid, st in hq.watcher.states.items():
                name = (st.get("attributes") or {}).get("friendly_name", "")
                if eid.split(".")[0] in ("light", "switch") and name and want in name.lower():
                    on = m.group(1).lower() == "accendi"
                    await self.call_service(eid.split(".")[0], "turn_on" if on else "turn_off", {"entity_id": eid})
                    return {"response": {"response_type": "action_done", "speech": {"plain": {"speech": f"{name}: {'accesa' if on else 'spenta'}"}}}}
        return {"response": {"response_type": "error", "data": {"code": "no_intent_match"}}}

    async def camera_stream(self, eid):
        """MJPEG like Home Assistant's camera_proxy_stream: a new frame twice a second."""
        import asyncio

        async def chunks():
            while True:
                frame, _ = await self.camera_image(eid)
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
                await asyncio.sleep(0.5)

        return "multipart/x-mixed-replace;boundary=frame", chunks()

    async def camera_image(self, eid):
        if eid.startswith("image."):
            im = Image.new("RGB", (640, 480), (10, 18, 30))
            dr = ImageDraw.Draw(im)
            rooms = [(60, 60, 330, 250, (40, 70, 110)), (330, 60, 580, 250, (55, 90, 70)), (60, 250, 260, 420, (90, 70, 50)), (260, 250, 580, 420, (70, 60, 100))]
            for x1, y1, x2, y2, c in rooms:
                dr.rectangle([x1, y1, x2, y2], fill=c, outline=(200, 220, 240), width=3)
            k = time.time() / 4
            path = [(120 + 10 * i, 120 + int(60 * math.sin(i / 3))) for i in range(int(k % 20) + 1)]
            if len(path) > 1:
                dr.line(path, fill=(150, 220, 255), width=6)
            x, y = path[-1]
            dr.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(255, 255, 255), outline=(79, 209, 255), width=3)
            dr.rectangle([500, 380, 540, 410], fill=(61, 220, 151))
            b = io.BytesIO()
            im.save(b, "JPEG", quality=85)
            return b.getvalue(), "image/jpeg"
        im = Image.new("RGB", (640, 360), (24, 44, 38))
        dr = ImageDraw.Draw(im)
        for y in range(0, 360, 6):
            dr.line([(0, y), (640, y)], fill=(30, 52, 46))
        dr.text((20, 330), f"{eid} {time.strftime('%H:%M:%S')}", fill=(220, 255, 230))
        b = io.BytesIO()
        im.save(b, "JPEG")
        return b.getvalue(), "image/jpeg"


hq.ha = REST()
uvicorn.run(create_app(s, hq=hq, start_workers=True), host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
