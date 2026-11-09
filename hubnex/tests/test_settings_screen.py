"""The settings screen: language, voice engine, voice and calendars chosen from lists in the dashboard
instead of typed in the add-on's options. The choices win over the add-on and survive a restart."""

import dataclasses
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from hubnex import i18n
from hubnex.config import load_org
from hubnex.hq import HQ
from hubnex.main import create_app
from hubnex.store import Store
from tests.conftest import FakeClient


def st(name):
    return {"state": "off", "attributes": {"friendly_name": name}, "last_changed": datetime.now(timezone.utc).isoformat()}


@pytest.fixture
def home(settings, make_hq):
    settings.voice_tts_entity = "tts.piper"  # what the add-on's options say
    settings.calendar_entities = {"calendar.nico"}
    hq = make_hq([])
    hq.watcher.states = {
        "tts.piper": st("Piper"), "tts.google_translate_nl_com": st("Google Translate nl"),
        "calendar.nico": st("Nico"), "calendar.danielle": st("Danielle"), "calendar.feestdagen": st("Feestdagen"),
        "light.keuken": st("Keuken"),
    }
    yield hq, TestClient(create_app(settings, hq=hq, start_workers=False)).__enter__()
    i18n.set_system_lang("it")


def test_the_screen_lists_what_there_is_to_choose_from(home):
    hq, client = home
    d = client.get("/api/settings").json()
    assert [t["e"] for t in d["options"]["tts"]] == ["tts.google_translate_nl_com", "tts.piper"]
    assert [c["n"] for c in d["options"]["calendars"]] == ["Danielle", "Feestdagen", "Nico"]
    assert d["options"]["languages"] == ["auto", "it", "en", "nl"]
    assert d["values"]["voice_tts_entity"] == "tts.piper" and d["values"]["calendar_entities"] == ["calendar.nico"]
    assert d["overrides"] == [], "nothing chosen here yet: the add-on's values rule"


def test_a_choice_wins_over_the_add_on_and_takes_effect_at_once(home):
    hq, client = home
    d = client.put("/api/settings", json={"voice_tts_entity": "tts.google_translate_nl_com", "voice_tts_voice": "Colette",
                                           "calendar_entities": ["calendar.danielle", "calendar.nico"]}).json()
    assert d["values"]["voice_tts_entity"] == "tts.google_translate_nl_com" and d["values"]["voice_tts_voice"] == "Colette"
    assert sorted(d["overrides"]) == ["calendar_entities", "voice_tts_entity", "voice_tts_voice"]
    assert d["addon"]["voice_tts_entity"] == "tts.piper", "the add-on's value is kept, to go back to"
    assert hq.settings.voice_tts_entity == "tts.google_translate_nl_com"
    assert hq.settings.calendar_entities == {"calendar.danielle", "calendar.nico"}, "the calendar tool reads this"
    assert hq.alerts.tts_engine() == "tts.google_translate_nl_com", "the spoken notifications use the chosen engine"


def test_null_goes_back_to_the_add_on_and_empty_means_none_or_all(home):
    hq, client = home
    client.put("/api/settings", json={"voice_tts_entity": "", "calendar_entities": []})
    assert hq.settings.voice_tts_entity == "" and hq.settings.calendar_entities == set(), "[] = every calendar"
    d = client.put("/api/settings", json={"voice_tts_entity": None, "calendar_entities": None}).json()
    assert hq.settings.voice_tts_entity == "tts.piper" and hq.settings.calendar_entities == {"calendar.nico"}
    assert d["overrides"] == []


def test_a_field_left_out_stays_as_it_is(home):
    hq, client = home
    client.put("/api/settings", json={"voice_tts_voice": "Colette"})
    client.put("/api/settings", json={"calendar_entities": ["calendar.danielle"]})
    assert hq.settings.voice_tts_voice == "Colette" and hq.settings.calendar_entities == {"calendar.danielle"}


def test_what_does_not_exist_is_refused_with_a_clear_message(home):
    hq, client = home
    r = client.put("/api/settings", json={"voice_tts_entity": "tts.bestaat_niet"})
    assert r.status_code == 422 and "tts.bestaat_niet" in r.json()["detail"]
    r = client.put("/api/settings", json={"calendar_entities": ["calendar.nico", "calendar.nope"]})
    assert r.status_code == 422 and "calendar.nope" in r.json()["detail"]
    assert client.put("/api/settings", json={"calendar_entities": ["light.keuken"]}).status_code == 422
    assert client.put("/api/settings", json={"language": "fr"}).status_code == 422
    assert hq.settings.calendar_entities == {"calendar.nico"}, "a refused save changes nothing"
    assert client.get("/api/settings").json()["overrides"] == []


def test_the_error_message_follows_the_viewers_language(home):
    hq, client = home
    r = client.put("/api/settings", json={"voice_tts_entity": "tts.nope"}, headers={"X-HubNEX-Lang": "nl"})
    assert r.json()["detail"] == "onbekende spraakengine: tts.nope"


def test_the_language_can_be_chosen_and_switched_back_to_automatic(home):
    hq, client = home
    client.put("/api/settings", json={"language": "en"})
    assert i18n.system_lang() == "en" and hq.settings.language == "en"
    hq.watcher.language = "nl"
    client.put("/api/settings", json={"language": "auto"})
    assert i18n.system_lang() == "nl", "automatic = Home Assistant's own"
    assert hq.watcher.on_language is i18n.set_system_lang


def test_the_choices_survive_a_restart(home, settings):
    hq, client = home
    original = dataclasses.replace(settings, voice_tts_entity="tts.piper", voice_tts_voice="", calendar_entities={"calendar.nico"},
                                   language="auto")  # as the add-on's options were before the first choice
    client.put("/api/settings", json={"voice_tts_entity": "tts.google_translate_nl_com", "calendar_entities": ["calendar.danielle"]})
    again = HQ(original, load_org(original.agents_file), Store(original.db_path), client=FakeClient([]))
    import asyncio
    asyncio.run(again.load())
    assert again.settings.voice_tts_entity == "tts.google_translate_nl_com"
    assert again.settings.calendar_entities == {"calendar.danielle"}
    assert again.settings_view()["addon"]["voice_tts_entity"] == "tts.piper"


def test_the_voices_of_an_engine_fill_the_dropdown(home):
    hq, client = home

    async def voices(engine):
        assert engine == "tts.google_translate_nl_com"
        return [{"id": "nl-NL-ColetteNeural", "name": "Colette"}, {"id": "nl-NL-FennaNeural", "name": "Fenna"}]

    hq.watcher.tts_voices = voices
    assert [v["name"] for v in client.get("/api/settings/voices", params={"engine": "tts.google_translate_nl_com"}).json()["voices"]] == ["Colette", "Fenna"]
    assert client.get("/api/settings/voices", params={"engine": "../etc/passwd"}).status_code == 422
    assert client.get("/api/settings/voices", params={"engine": "light.keuken"}).status_code == 422

    async def broken(engine):
        raise RuntimeError("engine offline")

    hq.watcher.tts_voices = broken
    r = client.get("/api/settings/voices", params={"engine": "tts.piper"})
    assert r.status_code == 502 and "engine offline" in r.json()["detail"]
