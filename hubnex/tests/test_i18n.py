"""English: every message of the add-on has its translation, and the add-on speaks it."""

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
def english():
    i18n.set_system_lang("en")
    yield
    i18n.set_system_lang("it")


def test_every_message_has_its_english():
    out = subprocess.run([sys.executable, "dev/i18n_keys.py", "--python", "--missing"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [], "messages without English: add them to hubnex/i18n_en.py"


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


async def test_jarvis_answers_in_english(make_hq, english):
    hq = make_hq([response([text_block("Done, Sir.")], "end_turn")])
    await hq.chat("t", "turn on the kitchen light")
    system = hq.client.requests[-1]["system"]
    assert "Rispondi sempre in inglese" in system and "Parli in italiano" not in system
    assert hq.agent_system(hq.org.agents[0]).count("Rispondi sempre in inglese") == 1


def test_api_errors_in_the_viewers_language(settings, make_hq):
    with TestClient(create_app(settings, hq=make_hq([]), start_workers=False)) as client:
        assert client.get("/api/agents/nobody").json()["detail"] == "agente sconosciuto"
        r = client.get("/api/agents/nobody", headers={"X-HubNEX-Lang": "en-GB"})
        assert r.json()["detail"] == "unknown agent"


def test_the_voice_reads_english(english):
    said = for_voice("Power 1.84 kW, today 9.6 kWh, 21.5°C, e.g. a UPS ≥ 10 kVA on 1/9/2026 ✅")
    assert said == ("Power 1.84 kilowatts, today 9.6 kilowatt hours, 21.5 degrees, for example a UPS "
                    "at least 10 kilovolt amperes on 1 September 2026.")
    assert for_voice("0,2 Ω", lang="it") == "0,2 ohm."


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
