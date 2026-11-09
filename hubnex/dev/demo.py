"""HubNEX with a pretend Home Assistant and a pretend Claude: for trying the dashboard,
taking screenshots and the browser tests. No real house, no API key, nothing leaves the machine.

    python dev/demo.py 8765            # then open http://127.0.0.1:8765
    python dev/demo.py 8765 casa.yaml  # with your own floor plan file
    DEMO_LANG=en python dev/demo.py 8765   # an English house and an English-speaking add-on
"""
import io, math, os, random, re, sys, tempfile, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from PIL import Image, ImageDraw, ImageFont

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
add("lock.ingresso", "corridoio", "locked", 22, friendly_name="Porta ingresso", code_format="^\\d{4}$")
add("lock.garage", "corridoio", "locked", 140, friendly_name="Porta garage")
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
add("weather.casa", None, "partlycloudy", temperature=14, humidity=62, wind_speed=11, wind_speed_unit="km/h", friendly_name="Meteo")
# the dishwasher finished a while ago (its plug's power dropped)
add("switch.lavastoviglie", "cucina", "on", 300, device="dev-dish", friendly_name="Lavastoviglie")
add("sensor.lavastoviglie_potenza", None, "2", 48, device="dev-dish", device_class="power", unit_of_measurement="W", friendly_name="Potenza lavastoviglie")
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
add("input_number.sacchi_pellet", "soggiorno", "7", 600, min=0, max=100, step=1, mode="box", unit_of_measurement="sacchi", friendly_name="Sacchi pellet")
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
    "Robot aspirapolvere": "Robot vacuum", "Mappa robot": "Robot map", "Altoparlante cucina": "Kitchen speaker",
    "Ingresso Veicolo in movimento": "Entrance vehicle moving", "Ingresso Persona": "Entrance person",
    "Pulisce il soggiorno": "Cleaning the living room", "Lavastoviglie": "Dishwasher", "Sacchi pellet": "Pellet bags",
    "Potenza lavastoviglie": "Dishwasher power", "Silenziosa": "Quiet", "Bilanciata": "Balanced",
}
if EN:  # the same house, in English
    for a in T.AREAS:
        a["name"] = NAMES_EN.get(a["name"], a["name"])
    for st in T.STATES:
        at = st["attributes"]
        at["friendly_name"] = NAMES_EN.get(at.get("friendly_name"), at.get("friendly_name"))
        for k in ("options", "fan_speed_list"):
            if k in at:
                at[k] = [NAMES_EN.get(o, o) for o in at[k]]
        for k in ("fan_speed", "status"):
            if k in at:
                at[k] = NAMES_EN.get(at[k], at[k])
    for dv in T.DEVICES:
        dv["name"] = NAMES_EN.get(dv.get("name"), dv.get("name"))

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


class _SlowStream(_Stream):
    """A stream that takes its time, as Claude does while it thinks (DEMO_WORK=4: four times longer)."""

    def __init__(self, resp, delay):
        super().__init__(resp)
        self.delay = delay * float(os.environ.get("DEMO_WORK") or 1)

    async def __aenter__(self):
        import asyncio
        await asyncio.sleep(self.delay)
        return self


# The scripted job: a quote, which Jarvis splits between Sales and the Accountant.
QUOTE_WORDS = ("quote", "preventivo")
SCRIPT = {
    "en": {
        "plan": "The quote is for Sales, the invoice check for the Accountant. I ask both.",
        "sales_task": "Draft the quote for the Rossi kitchen renovation: lighting, sockets, smart switches.",
        "acc_task": "Check whether the Rossi family's last invoice has been paid.",
        "sales_think": "Lighting, sockets and switches for a 14 m2 kitchen: I list the items and the labour.",
        "sales": "Quote ready: 6 LED spotlights, 8 sockets, 4 smart switches, labour. Total 2,340 EUR + VAT.",
        "acc_think": "I look for the latest Rossi invoice and its payment.",
        "acc": "Invoice 112 of 3 October: paid on 18 October, nothing outstanding.",
        "done": "Done. The Rossi quote is ready: 2,340 EUR + VAT, with LED spotlights, sockets and smart "
                "switches. Their last invoice is paid, nothing outstanding. Shall I send them the quote?",
    },
    "it": {
        "plan": "Il preventivo è per il Commerciale, la fattura per il Contabile. Li sento entrambi.",
        "sales_task": "Prepara il preventivo per la cucina dei Rossi: illuminazione, prese, interruttori smart.",
        "acc_task": "Controlla se l'ultima fattura della famiglia Rossi è stata pagata.",
        "sales_think": "Luci, prese e interruttori per una cucina di 14 m2: elenco materiali e manodopera.",
        "sales": "Preventivo pronto: 6 faretti LED, 8 prese, 4 interruttori smart, manodopera. Totale 2.340 EUR + IVA.",
        "acc_think": "Cerco l'ultima fattura Rossi e il suo pagamento.",
        "acc": "Fattura 112 del 3 ottobre: pagata il 18 ottobre, nessun sospeso.",
        "done": "Fatto. Il preventivo Rossi è pronto: 2.340 EUR + IVA, con faretti LED, prese e interruttori "
                "smart. L'ultima fattura è pagata, nessun sospeso. Vuoi che gli mandi il preventivo?",
    },
}


def demo_card(request: str) -> dict:
    """What the demo's Claude composes when asked for a card: the stove (plus one entity made up,
    which HubNEX must leave out)."""
    return {"name": "Stove" if EN else "Stufa", "color": "warm", "blocks": [
        {"kind": "value", "entity": "climate.soggiorno", "label": "", "w": 2, "h": 2, "rules": [{"op": ">", "v": "23", "c": "red"}, {"op": "<", "v": "19", "c": "cool"}]},
        {"kind": "toggle", "entity": "input_boolean.stufa_automatica", "label": "", "w": 1, "h": 1},
        {"kind": "ring", "entity": "input_number.stufa_potenza", "label": "", "w": 1, "h": 1, "min": 1, "max": 5},
        {"kind": "bar", "entity": "input_number.sacchi_pellet", "label": "Pellet", "w": 2, "h": 1, "min": 0, "max": 20,
         "rules": [{"op": "<", "v": "5", "c": "red"}], "tap": {"do": "ask", "text": "Quando devo ordinare il pellet?"}},
        {"kind": "band", "entity": "input_datetime.stufa_accensione", "entity2": "input_datetime.stufa_spegnimento", "label": "", "w": 4, "h": 1},
        {"kind": "select", "entity": "input_select.stufa_modo", "label": "", "w": 2, "h": 1},
        {"kind": "toggle", "entity": "switch.stufa_inventata", "label": "", "w": 1, "h": 1},
        {"kind": "ask", "entity": "", "label": "Quanto pellet mi resta?", "w": 2, "h": 1},
    ]}


class DemoClaude(FakeClient):
    """Claude stand-in: one polite sentence, whatever is asked; a request for a quote plays the
    team at work (Jarvis delegates to Sales and the Accountant, then sums up)."""

    async def _create(self, **kwargs):
        import json as _json
        self.requests.append(kwargs)
        if "Componi card" in str(kwargs.get("system")):
            import asyncio
            await asyncio.sleep(1.5)  # as if Claude were thinking
            return response([text_block(_json.dumps(demo_card(str(kwargs["messages"][-1]["content"]))))], "end_turn")
        return response([text_block("{}")], "end_turn")

    def _stream(self, **kwargs):
        from types import SimpleNamespace as NS
        from hubnex.hq import QUICK_PASS
        self.requests.append(kwargs)
        sc = SCRIPT["en" if EN else "it"]
        msgs = kwargs.get("messages") or []
        tools = {t.get("name") for t in kwargs.get("tools") or [] if isinstance(t, dict)}
        first = str(msgs[0].get("content")) if msgs else ""
        last = msgs[-1].get("content") if msgs else ""
        asked = str(msgs[-1]) if msgs else ""
        quote = any(w in asked.lower() or w in first.lower() for w in QUOTE_WORDS)
        think = lambda t: NS(type="thinking", thinking=t)
        if quote and tools and all(n.startswith("ha_") for n in tools):  # the quick route: this is for Jarvis
            return _Stream(response([text_block(QUICK_PASS)], "end_turn"))
        if quote and "delegate" in tools:
            if isinstance(last, list) and any(getattr(b, "type", None) == "tool_result" or (isinstance(b, dict) and b.get("type") == "tool_result") for b in last):
                return _SlowStream(response([think(sc["done"][:60]), text_block(sc["done"])], "end_turn"), 1.2)
            return _SlowStream(response([
                think(sc["plan"]),
                NS(type="tool_use", name="delegate", input={"agent_id": "sales" if EN else "commerciale", "task": sc["sales_task"]}, id="toolu_s"),
                NS(type="tool_use", name="delegate", input={"agent_id": "accountant" if EN else "contabile", "task": sc["acc_task"]}, id="toolu_a"),
            ], "tool_use"), 1.5)
        if sc["sales_task"] in first:
            return _SlowStream(response([think(sc["sales_think"]), text_block(sc["sales"])], "end_turn"), 3.5)
        if sc["acc_task"] in first:
            return _SlowStream(response([think(sc["acc_think"]), text_block(sc["acc"])], "end_turn"), 3.0)
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
    card = {"id": "c1", "name": NAMES_EN["Ingresso"] if EN else "Ingresso", "entities": ["camera.ingresso", "binary_sensor.ingresso_veicolo", "binary_sensor.ingresso_persona"], "size": "wide"}
    adjust = {"extra": {}, "hidden": {}, "cards": {"giardino": [card]}}
    hq.store._conn.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", ("casa_adjust", json.dumps(adjust)))
    hq.store._conn.commit()


seed_cards()


def seed_deadlines() -> None:
    """A few work deadlines, for the "today" card (made up)."""
    now = datetime.now()
    rows = [
        (-1, "Invio verbale verifica illuminazione di sicurezza", "Send the emergency lighting test report"),
        (0, "Sopralluogo quadro elettrico, ore 15:00", "Site visit to the switchboard, 3 pm"),
        (1, "Consegna offerta contratto di manutenzione", "Deliver the maintenance contract offer"),
        (4, "Rinnovo polizza RC professionale", "Renew the professional liability policy"),
        (20, "Verifica impianto di terra", "Earthing system inspection"),
    ]
    for days, it, en in rows:
        due = (now + timedelta(days=days)).strftime("%Y-%m-%d")
        hq.store._conn.execute("INSERT INTO deadlines (title, due, created) VALUES (?, ?, ?)", (en if EN else it, due, time.time()))
    hq.store._conn.commit()


seed_deadlines()


async def demo_phones():
    return [{"service": "mobile_app_pixel_9", "name": "Pixel 9"}, {"service": "mobile_app_ipad", "name": "iPad"}]


hq.watcher.phones = demo_phones


class REST:
    enabled = True
    blocked = set()

    async def close(self):
        pass

    async def forecast(self, eid):
        days = [("partlycloudy", 17, 9, 10), ("rainy", 14, 10, 80), ("cloudy", 15, 9, 30), ("sunny", 18, 8, 0), ("sunny", 19, 9, 0), ("partlycloudy", 17, 10, 10)]
        start = datetime.now(timezone.utc)
        return [{"datetime": (start + timedelta(days=i)).isoformat(), "condition": c, "temperature": hi, "templow": lo, "precipitation_probability": p}
                for i, (c, hi, lo, p) in enumerate(days)]

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
        if eids == ["input_number.sacchi_pellet"]:  # a delivery of 15, 6 days ago, then about 1.4 a day
            pts, v = [], 33
            for d in range(30, 0, -1):
                v = v + 15 if d == 6 else v - (2 if d % 3 == 0 else 1)  # 1-2 bags a day
                pts.append(((now - timedelta(days=d)).isoformat(), str(max(v, 0))))
            pts.append((now.isoformat(), hq.watcher.states[eids[0]]["state"]))
            return {eids[0]: pts}
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
        """MJPEG like Home Assistant's camera_proxy_stream: four frames a second."""
        import asyncio

        async def chunks():
            await asyncio.sleep(2)  # like a real camera: the first frame takes a while
            while True:
                frame, _ = await self.camera_image(eid)
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
                await asyncio.sleep(0.25)

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
        # a live mosaic, as when a camera is censored for privacy: blocks that shift slowly
        t = time.time()
        rng = random.Random(eid)
        base = (52, 62, 70) if eid.endswith("ingresso") else (74, 64, 56)
        im = Image.new("RGB", (640, 360))
        dr = ImageDraw.Draw(im)
        for gy in range(12):
            for gx in range(20):
                ph, sp, amp = rng.uniform(0, 6.3), rng.uniform(0.6, 1.8), rng.uniform(10, 34)
                v = amp * math.sin(t * sp + ph)
                tint = rng.uniform(-14, 14)
                c = tuple(max(0, min(255, int(b + v + tint))) for b in base)
                dr.rectangle([gx * 32, gy * 32, gx * 32 + 31, gy * 32 + 31], fill=c)
        label = "CENSORED FOR PRIVACY" if EN else "CENSURATO PER PRIVACY"
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
        except OSError:
            font = ImageFont.load_default(30)
        w = dr.textlength(label, font=font)
        dr.rectangle([0, 152, 640, 208], fill=(0, 0, 0))
        dr.text(((640 - w) / 2, 163), label, fill=(240, 240, 240), font=font)
        dr.rectangle([0, 0, 640, 24], fill=(0, 0, 0))
        dr.text((10, 6), time.strftime("%Y-%m-%d %H:%M:%S"), fill=(235, 235, 235))
        dr.text((580, 6), "CAM 1" if eid.endswith("ingresso") else "CAM 2", fill=(235, 235, 235))
        b = io.BytesIO()
        im.save(b, "JPEG")
        return b.getvalue(), "image/jpeg"


hq.ha = REST()
uvicorn.run(create_app(s, hq=hq, start_workers=True), host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
