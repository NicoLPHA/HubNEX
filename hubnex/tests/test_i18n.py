"""English and Dutch: every message of the add-on has its translation, and the add-on speaks it."""

import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from hubnex import i18n
from hubnex.main import create_app
from hubnex.speech import for_voice
from tests.conftest import ROOT, response, text_block


@pytest.fixture
def dutch():
    i18n.set_system_lang("nl")
    yield
    i18n.set_system_lang("it")


@pytest.fixture
def english():
    i18n.set_system_lang("en")
    yield
    i18n.set_system_lang("it")


def test_every_message_has_its_english():
    out = subprocess.run([sys.executable, "dev/i18n_keys.py", "--python", "--missing"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [], "messages without English: add them to hubnex/i18n_en.py"


def test_every_message_has_its_dutch():
    out = subprocess.run([sys.executable, "dev/i18n_keys.py", "--python", "--missing", "--lang", "nl"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [], "messages without Dutch: add them to hubnex/i18n_nl.py"


def test_dutch_keeps_the_placeholders_of_the_english():
    import re
    from hubnex.i18n_en import EN
    from hubnex.i18n_nl import NL
    holes = lambda text: sorted(re.findall(r"\{\w+\}", text))  # noqa: E731
    assert [k for k in EN if holes(NL[k]) != holes(k)] == []
    assert set(NL) == set(EN), "Dutch and English must translate the same messages"


def test_tr_follows_the_request_then_the_add_on():
    assert i18n.tr("bozza sconosciuta") == "bozza sconosciuta"
    token = i18n.REQUEST_LANG.set("en")
    try:
        assert i18n.tr("bozza sconosciuta") == "unknown draft"
        assert i18n.tr("inviata alle {time}", time="10:00") == "sent at 10:00"
        assert i18n.tr_sys("bozza sconosciuta") == "bozza sconosciuta"  # the add-on is in Italian
    finally:
        i18n.REQUEST_LANG.reset(token)
    assert i18n.norm("en-GB") == "en" and i18n.norm("it-IT") == "it" and i18n.norm("de") == "en"
    assert i18n.norm("nl-NL") == "nl" and i18n.norm("nl") == "nl" and i18n.norm("nl-BE") == "nl"
    token = i18n.REQUEST_LANG.set("nl")
    try:
        assert i18n.tr("bozza sconosciuta") == "onbekend concept"
        assert i18n.tr("inviata alle {time}", time="10:00") == "verstuurd om 10:00"
    finally:
        i18n.REQUEST_LANG.reset(token)


async def test_jarvis_answers_in_english(make_hq, english):
    hq = make_hq([response([text_block("Done, Sir.")], "end_turn")])
    await hq.chat("t", "turn on the kitchen light")
    system = hq.client.requests[-1]["system"]
    assert "Rispondi sempre in inglese" in system and "Parli in italiano" not in system
    assert hq.agent_system(hq.org.agents[0]).count("Rispondi sempre in inglese") == 1


async def test_jarvis_answers_in_dutch(make_hq, dutch):
    hq = make_hq([response([text_block("Klaar.")], "end_turn")])
    await hq.chat("t", "doe het licht in de keuken aan")
    system = hq.client.requests[-1]["system"]
    assert "Rispondi sempre in olandese (Nederlands)" in system and "Parli in italiano" not in system
    assert "inglese" not in system.split("Rispondi sempre in")[1].split(",")[0]


def test_dutch_requests_for_the_door_or_the_alarm_go_to_jarvis():
    """Doors and alarms never take the quick route: Jarvis asks for confirmation (also in Dutch)."""
    from hubnex.hq import SENSITIVE
    for text in ("ontgrendel de voordeur", "doe de garagedeur open", "zet het alarm uit", "open de poort", "unlock the door"):
        assert SENSITIVE.search(text), text
    for text in ("doe het licht aan in de woonkamer", "open de gordijnen", "doe de rolluiken open", "zet het alarm aan"):
        assert not SENSITIVE.search(text), text


def test_api_errors_in_the_viewers_language(settings, make_hq):
    with TestClient(create_app(settings, hq=make_hq([]), start_workers=False)) as client:
        assert client.get("/api/agents/nobody").json()["detail"] == "agente sconosciuto"
        r = client.get("/api/agents/nobody", headers={"X-HubNEX-Lang": "en-GB"})
        assert r.json()["detail"] == "unknown agent"
        r = client.get("/api/agents/nobody", headers={"X-HubNEX-Lang": "nl-NL"})
        assert r.json()["detail"] == "onbekende agent"


def test_the_voice_reads_english(english):
    said = for_voice("Power 1.84 kW, today 9.6 kWh, 21.5°C, e.g. a UPS ≥ 10 kVA on 1/9/2026 ✅")
    assert said == ("Power 1.84 kilowatts, today 9.6 kilowatt hours, 21.5 degrees, for example a UPS "
                    "at least 10 kilovolt amperes on 1 September 2026.")
    assert for_voice("0,2 Ω", lang="it") == "0,2 ohm."


def test_the_voice_reads_dutch(dutch):
    said = for_voice("Vermogen 1,84 kW, vandaag 9,6 kWh, 21,5°C, bijv. een UPS van 10 kVA op 1/9/2026 ✅")
    assert said == ("Vermogen 1,84 kilowatt, vandaag 9,6 kilowattuur, 21,5 graden, bijvoorbeeld een UPS van "
                    "10 kilovoltampère op 1 september 2026.")
    assert for_voice("1/300", lang="nl") == "1 op 300."


def test_energy_bands_are_italian_only_by_default(english):
    from hubnex.energy import clean_config
    assert clean_config({})["band_mode"] == "single"
    assert clean_config({"band_mode": "arera"})["band_mode"] == "arera"  # chosen on purpose
    i18n.set_system_lang("it")
    assert clean_config({})["band_mode"] == "arera"


def test_english_example_team(tmp_path, monkeypatch):
    from hubnex import config
    from hubnex.config import load_org
    org = load_org(str(config.DEFAULT_AGENTS_EN))
    assert org.boss_name == "Jarvis" and {c.name for c in org.companies} == {"Work", "Home"}
    assert {a.id for a in org.agents} == {a.id for a in load_org(str(config.DEFAULT_AGENTS)).agents} - {
        "contabile", "commerciale", "tecnico", "maggiordomo", "sentinella"} | {"accountant", "sales", "technical", "butler", "sentinel"}
    # first start of the add-on: the example in Home Assistant's language
    storage = tmp_path / "core.config"
    storage.write_text(json.dumps({"data": {"language": "en-GB"}}))
    assert config.ha_language(str(storage)) == "en-GB"
    opts, cfg = tmp_path / "options.json", tmp_path / "cfg"
    opts.write_text("{}")
    cfg.mkdir()
    monkeypatch.setattr(config, "ha_language", lambda storage=None: "en")
    monkeypatch.delenv("HUBNEX_LANGUAGE", raising=False)
    import os
    saved = dict(os.environ)
    for k in ("HUBNEX_AGENTS_FILE", "HUBNEX_CASA_FILE", "HUBNEX_DB", "HUBNEX_INTERNAL_TOKEN"):
        os.environ.pop(k, None)
    try:
        assert config._load_addon_options(str(opts), str(cfg))
        assert "Jarvis Butler" in (cfg / "agents.yaml").read_text()
    finally:  # the add-on sets its environment: give the other tests theirs back
        os.environ.clear()
        os.environ.update(saved)


def test_dutch_example_team(tmp_path, monkeypatch):
    from hubnex import config
    from hubnex.config import load_org
    org = load_org(str(config.DEFAULT_AGENTS_NL))
    assert org.boss_name == "Jarvis" and len(org.companies) == 2
    assert len(org.agents) == len(load_org(str(config.DEFAULT_AGENTS)).agents)
    # first start of the add-on in a Dutch Home Assistant: the Dutch example team
    opts, cfg = tmp_path / "options.json", tmp_path / "cfg"
    opts.write_text("{}")
    cfg.mkdir()
    monkeypatch.setattr(config, "ha_language", lambda storage=None: "nl")
    monkeypatch.delenv("HUBNEX_LANGUAGE", raising=False)
    import os
    saved = dict(os.environ)
    for k in ("HUBNEX_AGENTS_FILE", "HUBNEX_CASA_FILE", "HUBNEX_DB", "HUBNEX_INTERNAL_TOKEN"):
        os.environ.pop(k, None)
    try:
        assert config._load_addon_options(str(opts), str(cfg))
        assert (cfg / "agents.yaml").read_text(encoding="utf-8") == config.DEFAULT_AGENTS_NL.read_text(encoding="utf-8")
    finally:
        os.environ.clear()
        os.environ.update(saved)
