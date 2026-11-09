from datetime import datetime, timedelta, timezone

import pytest

from hubnex.alerts import clean_config, in_window
from tests.conftest import FakeTeam

T0 = datetime(2026, 11, 10, 18, 0)


def st(state, dc=None, name=None, changed=None, **attrs):
    a = dict(attrs)
    if dc:
        a["device_class"] = dc
    if name:
        a["friendly_name"] = name
    return {"state": state, "attributes": a, "last_changed": (changed or datetime.now(timezone.utc)).isoformat()}


@pytest.fixture
def house(make_hq):
    team = FakeTeam()
    hq = make_hq([], team=team)
    hq.watcher.states = {
        "binary_sensor.finestra_cucina": st("off", "window", "Finestra cucina"),
        "climate.soggiorno": st("heat", hvac_action="idle"),
        "person.anna": st("home"),
        "lock.ingresso": st("locked", name="Porta d'ingresso"),
        "binary_sensor.perdita_lavatrice": st("off", "moisture", "Lavatrice"),
        "light.soffitto": st("off", name="Soffitto"),
        "sensor.termostato_batteria": st("80", "battery", "Termostato", unit_of_measurement="%"),
    }
    hq.watcher.ready.set()
    calls = []

    async def call_service(domain, service, data=None, by_owner=False):
        calls.append((domain, service, data, by_owner))
        return []

    hq.ha.call_service = call_service
    hq.alerts.phones = [{"service": "mobile_app_pixel", "name": "Pixel"}]
    clock = {"now": T0}
    hq.now = lambda: clock["now"].replace(tzinfo=hq.tz)

    def at(minutes):
        clock["now"] = T0 + timedelta(minutes=minutes)

    return hq, team, calls, at


def pushes(calls, kind=None):
    out = [c for c in calls if c[0] == "notify" and c[1] == "mobile_app_pixel"]
    return [c for c in out if (c[2]["message"] == "clear_notification") == (kind == "clear")]


async def test_window_open_with_heating_waits_then_warns_then_clears(house):
    hq, team, calls, at = house
    hq.watcher.states["binary_sensor.finestra_cucina"]["state"] = "on"
    await hq.alerts.tick()
    assert not calls  # heating idle: nothing wrong
    hq.watcher.states["climate.soggiorno"]["attributes"]["hvac_action"] = "heating"
    await hq.alerts.tick()
    at(3)
    await hq.alerts.tick()
    assert not pushes(calls), "waits the 5 minutes"
    at(6)
    await hq.alerts.tick()
    [push] = pushes(calls)
    assert push[2]["title"] == "Finestre aperte"
    assert "Finestra cucina" in push[2]["message"] and "riscaldamento" in push[2]["message"]
    assert push[2]["data"]["tag"] == "hubnex_windows"
    assert len(team.posts) == 1
    at(7)
    await hq.alerts.tick()
    assert len(pushes(calls)) == 1, "once per episode"
    hq.watcher.states["binary_sensor.finestra_cucina"]["state"] = "off"
    await hq.alerts.tick()
    [clear] = pushes(calls, "clear")
    assert clear[2]["data"]["tag"] == "hubnex_windows"
    # back within 30 minutes: no new warning (a window opened and closed again)
    hq.watcher.states["binary_sensor.finestra_cucina"]["state"] = "on"
    at(20)
    await hq.alerts.tick()
    at(30)
    await hq.alerts.tick()
    assert len(pushes(calls)) == 1


async def test_leak_warns_at_once_even_in_quiet_hours(house):
    hq, team, calls, at = house
    await hq.alerts.save({"quiet": {"from": "17:00", "to": "07:00"}})
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    await hq.alerts.tick()
    [push] = pushes(calls)
    assert "Perdita d'acqua" in push[2]["title"] and "Lavatrice" in push[2]["message"]
    assert push[2]["data"]["priority"] == "high"
    assert any(c[:2] == ("persistent_notification", "create") for c in calls)


async def test_quiet_hours_hold_the_rest_until_they_end(house):
    hq, team, calls, at = house
    await hq.alerts.save({"quiet": {"from": "17:00", "to": "19:00"}})
    hq.watcher.states["sensor.termostato_batteria"]["state"] = "9"
    await hq.alerts.tick()
    at(40)
    await hq.alerts.tick()
    assert not pushes(calls)
    at(61)
    await hq.alerts.tick()
    [push] = pushes(calls)
    assert "Termostato 9%" in push[2]["message"]


async def test_nobody_home_lock_open_and_the_close_button(house):
    hq, team, calls, at = house
    hq.watcher.states["person.anna"]["state"] = "not_home"
    hq.watcher.states["lock.ingresso"]["state"] = "unlocked"
    await hq.alerts.tick()
    at(6)
    await hq.alerts.tick()
    [push] = pushes(calls)
    [button] = push[2]["data"]["actions"]
    assert button["title"] == "Chiudi" and button["action"].startswith("HUBNEX_")
    assert team.posts[-1]["buttons"][0][0][1].startswith("h:")
    # pressed on the phone: Home Assistant sends the event, HubNEX locks
    await hq._ha_event("app_action", button["action"], {"action": button["action"]})
    assert ("lock", "lock", {"entity_id": "lock.ingresso"}, True) in calls
    # a second press does nothing
    n = len(calls)
    await hq._ha_event("app_action", button["action"], {"action": button["action"]})
    assert len(calls) == n


async def test_lights_at_night_offer_to_turn_them_off(house):
    hq, team, calls, at = house
    hq.watcher.states["light.soffitto"]["state"] = "on"
    at(60 * 6)  # 00:00
    await hq.alerts.tick()
    at(60 * 6 + 16)
    await hq.alerts.tick()
    [push] = pushes(calls)
    assert "Soffitto" in push[2]["message"]
    tok = push[2]["data"]["actions"][0]["action"][7:]
    await hq.alerts.press(tok)
    assert ("light", "turn_off", {"entity_id": ["light.soffitto"]}, True) in calls


async def test_offline_devices_use_home_assistants_clock(house):
    hq, team, calls, at = house
    now = hq.now()
    hq.watcher.states["light.soffitto"] = st("unavailable", name="Soffitto", changed=now - timedelta(hours=3))
    hq.watcher.states["light.nuova"] = st("unavailable", name="Nuova", changed=now - timedelta(minutes=2))  # not yet
    await hq.alerts.tick()
    [push] = pushes(calls)
    assert "Soffitto" in push[2]["message"] and "Nuova" not in push[2]["message"]


async def test_power_above_the_threshold(house):
    hq, team, calls, at = house
    hq.watcher.states["sensor.potenza"] = st("3.4", "power", "Potenza", unit_of_measurement="kW")
    hq.casa.adjust["energy"] = {"power": "sensor.potenza"}
    await hq.alerts.tick()
    at(11)
    await hq.alerts.tick()
    [push] = pushes(calls)
    assert "3,4 kW" in push[2]["message"]


async def test_excluded_entities_and_switched_off_rules(house):
    hq, team, calls, at = house
    await hq.alerts.save({"exclude": ["binary_sensor.perdita_lavatrice"], "rules": {"battery": {"on": False}}})
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    hq.watcher.states["sensor.termostato_batteria"]["state"] = "5"
    at(60)
    await hq.alerts.tick()
    assert not pushes(calls)


def test_config_is_cleaned():
    c = clean_config({"quiet": {"from": "25:00", "to": "07:00"}, "phones": ["mobile_app_x", "notify.evil"],
                      "rules": {"power": {"watts": "50", "minutes": "abc", "app": 0}}})
    assert c["quiet"] == {"from": "", "to": "07:00"}
    assert c["phones"] == ["mobile_app_x"]
    assert c["rules"]["power"]["watts"] == 100 and c["rules"]["power"]["minutes"] == 10
    assert c["rules"]["power"]["app"] is False
    assert clean_config(None)["phones"] is None


def test_time_windows_across_midnight():
    assert in_window(datetime(2026, 1, 1, 23, 45), "23:30", "06:00")
    assert in_window(datetime(2026, 1, 1, 2, 0), "23:30", "06:00")
    assert not in_window(datetime(2026, 1, 1, 12, 0), "23:30", "06:00")
    assert not in_window(datetime(2026, 1, 1, 12, 0), "", "")


async def test_people_unknown_while_home_assistant_restarts_is_not_away(house):
    hq, team, calls, at = house
    hq.watcher.states["person.anna"]["state"] = "unknown"
    hq.watcher.states["lock.ingresso"]["state"] = "unlocked"
    await hq.alerts.tick()
    at(10)
    await hq.alerts.tick()
    assert not pushes(calls)


async def test_battery_says_which_device_and_where(house):
    hq, team, calls, at = house
    hq.watcher.states["sensor.batteria_5"] = st("8", "battery", "Batteria", unit_of_measurement="%")
    hq.watcher.entities["sensor.batteria_5"] = {"entity_id": "sensor.batteria_5", "device_id": "d1"}
    hq.watcher.devices["d1"] = {"id": "d1", "name": "Sensore porta", "area_id": "ingresso"}
    hq.watcher.areas["ingresso"] = {"area_id": "ingresso", "name": "Ingresso"}
    await hq.alerts.tick()
    at(31)
    await hq.alerts.tick()
    [push] = pushes(calls)
    assert "Sensore porta (Ingresso) 8%" in push[2]["message"]


async def test_no_emoji_in_the_messages(house):
    hq, team, calls, at = house
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    await hq.alerts.tick()
    texts = [team.posts[-1]["text"]] + [c[2]["title"] + c[2]["message"] for c in pushes(calls)]
    assert team.posts[-1]["text"].startswith("URGENTE: Perdita d'acqua")
    assert all(ch.isascii() or ch.isalpha() or ch in "àèéìòù'’ " for t in texts for ch in t)


async def test_pellet_below_the_threshold_asks_to_reorder_once(house):
    hq, team, calls, at = house
    hq.watcher.states["counter.carico_pellet"] = st("6", name="Carico pellet")  # a counter, by name a stock
    assert hq.casa.stocks() == ["counter.carico_pellet"]
    await hq.alerts.tick()
    assert pushes(calls) == []  # 6 > 5
    hq.watcher.states["counter.carico_pellet"] = st("5", name="Carico pellet")
    await hq.alerts.tick()
    [push] = pushes(calls)
    assert "Carico pellet: ne restano 5, sotto la soglia di 5" in push[2]["message"]
    hq.watcher.states["counter.carico_pellet"] = st("4", name="Carico pellet")
    at(30)
    await hq.alerts.tick()
    assert len(pushes(calls)) == 1  # one warning per episode
    hq.watcher.states["counter.carico_pellet"] = st("19", name="Carico pellet")  # the delivery came
    at(60)
    await hq.alerts.tick()
    assert len(pushes(calls, "clear")) == 1
    await hq.casa.set_stock("counter.carico_pellet", 15, 20)  # the owner's own threshold
    assert hq.casa.stock_of("counter.carico_pellet") == {"delivery": 15, "low": 20}

# ---------------------------------------------------------------------- spoken on speakers (Sonos…)
def spoken(calls):
    return [c for c in calls if c[:2] == ("tts", "speak")]


def with_speakers(hq):
    hq.watcher.states["media_player.woonkamer"] = st("idle", name="Woonkamer")
    hq.watcher.states["media_player.slaapkamer"] = st("off", name="Slaapkamer")
    hq.watcher.states["tts.piper"] = st("unknown")


async def test_speaker_is_off_until_it_is_switched_on(house):
    hq, team, calls, at = house
    with_speakers(hq)
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    await hq.alerts.tick()
    assert pushes(calls) and not spoken(calls), "the phone is warned, nothing is said aloud"
    assert hq.alerts.cfg["speaker"] == {"on": False, "players": [], "tts": "", "volume": 0}


async def test_a_leak_is_read_aloud_on_the_chosen_speakers_only(house):
    hq, team, calls, at = house
    with_speakers(hq)
    await hq.alerts.save({"speaker": {"on": True, "players": ["media_player.woonkamer"]}})
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    await hq.alerts.tick()
    [say] = spoken(calls)
    data = say[2]
    assert data["entity_id"] == "tts.piper"
    assert data["media_player_entity_id"] == ["media_player.woonkamer"]
    assert "Lavatrice" in data["message"] and len(data["message"]) <= 300
    assert not any(c[:2] == ("media_player", "volume_set") for c in calls), "volume untouched when 0"


async def test_only_rules_with_the_speaker_flag_speak(house):
    hq, team, calls, at = house
    with_speakers(hq)
    await hq.alerts.save({"speaker": {"on": True, "players": ["media_player.woonkamer"]}})
    hq.watcher.states["sensor.termostato_batteria"]["state"] = "9"
    await hq.alerts.tick()
    at(31)
    await hq.alerts.tick()
    assert pushes(calls) and not spoken(calls), "the battery rule does not speak by default"


async def test_switching_the_speaker_on_for_a_rule_makes_it_speak(house):
    hq, team, calls, at = house
    with_speakers(hq)
    await hq.alerts.save({"speaker": {"on": True, "players": ["media_player.woonkamer"]}, "rules": {"battery": {"speaker": True}}})
    hq.watcher.states["sensor.termostato_batteria"]["state"] = "9"
    await hq.alerts.tick()
    at(31)
    await hq.alerts.tick()
    assert len(spoken(calls)) == 1


async def test_volume_is_set_before_the_warning(house):
    hq, team, calls, at = house
    with_speakers(hq)
    await hq.alerts.save({"speaker": {"on": True, "players": ["media_player.woonkamer"], "volume": 40}})
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    await hq.alerts.tick()
    order = [c[:2] for c in calls if c[:2] in (("media_player", "volume_set"), ("tts", "speak"))]
    assert order == [("media_player", "volume_set"), ("tts", "speak")]
    assert [c for c in calls if c[1] == "volume_set"][0][2] == {"entity_id": ["media_player.woonkamer"], "volume_level": 0.4}


async def test_no_speaker_or_no_engine_never_breaks_the_warning(house):
    hq, team, calls, at = house
    hq.watcher.states["media_player.woonkamer"] = st("idle", name="Woonkamer")  # no tts engine at all
    await hq.alerts.save({"speaker": {"on": True, "players": ["media_player.woonkamer"]}})
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    await hq.alerts.tick()
    assert pushes(calls) and not spoken(calls)
    await hq.alerts.save({"speaker": {"on": True, "players": []}})  # on, but no speaker chosen
    assert await hq.alerts._speak("ciao") is False


async def test_a_failing_speaker_does_not_stop_the_other_channels(house):
    hq, team, calls, at = house
    with_speakers(hq)
    original = hq.ha.call_service

    async def broken(domain, service, data=None, by_owner=False):
        if (domain, service) == ("tts", "speak"):
            raise RuntimeError("speaker offline")
        return await original(domain, service, data, by_owner)

    hq.ha.call_service = broken
    await hq.alerts.save({"speaker": {"on": True, "players": ["media_player.woonkamer"]}})
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    await hq.alerts.tick()
    assert pushes(calls) and len(team.posts) == 1


async def test_a_leak_is_spoken_in_the_quiet_hours_the_rest_is_not(house):
    hq, team, calls, at = house
    with_speakers(hq)
    await hq.alerts.save({"quiet": {"from": "17:00", "to": "19:00"}, "speaker": {"on": True, "players": ["media_player.woonkamer"]},
                          "rules": {"battery": {"speaker": True}}})
    hq.watcher.states["sensor.termostato_batteria"]["state"] = "9"
    at(40)
    await hq.alerts.tick()
    assert not spoken(calls), "the battery waits for the end of the quiet hours"
    hq.watcher.states["binary_sensor.perdita_lavatrice"]["state"] = "on"
    await hq.alerts.tick()
    assert len(spoken(calls)) == 1, "a leak is always said"


async def test_the_test_notification_includes_the_speaker(house):
    hq, team, calls, at = house
    with_speakers(hq)
    await hq.alerts.save({"speaker": {"on": True, "players": ["media_player.woonkamer"]}})
    assert "Altoparlante" in await hq.alerts.test()
    assert len(spoken(calls)) == 1


async def test_the_popup_lists_speakers_and_engines(house):
    hq, team, calls, at = house
    with_speakers(hq)
    o = await hq.alerts.overview()
    assert [p["e"] for p in o["speaker"]["players"]] == ["media_player.slaapkamer", "media_player.woonkamer"]
    assert o["speaker"]["tts_choices"] == ["tts.piper"] and o["speaker"]["tts"] == "tts.piper"


async def test_the_engine_prefers_the_language_and_the_owners_choice(house):
    from hubnex import i18n

    hq, team, calls, at = house
    hq.watcher.states["tts.google_translate_en_com"] = st("unknown")
    hq.watcher.states["tts.google_translate_nl_nl"] = st("unknown")
    hq.watcher.states["tts.home_assistant_cloud"] = st("unknown")
    i18n.set_system_lang("nl")
    try:
        assert hq.alerts.tts_engine() == "tts.google_translate_nl_nl"
        await hq.alerts.save({"speaker": {"tts": "tts.home_assistant_cloud"}})
        assert hq.alerts.tts_engine() == "tts.home_assistant_cloud"
    finally:
        i18n.set_system_lang("it")


def test_speaker_config_is_cleaned():
    c = clean_config({"speaker": {"on": 1, "players": ["media_player.a", "light.x", 5, "media_player.a"], "tts": "tts.x", "volume": "150"}})
    assert c["speaker"] == {"on": True, "players": ["media_player.a"], "tts": "tts.x", "volume": 100}
    assert clean_config({"speaker": {"tts": "notify.evil", "volume": "abc"}})["speaker"] == {"on": False, "players": [], "tts": "", "volume": 0}
    assert clean_config(None)["rules"]["safety"]["speaker"] is True and clean_config(None)["rules"]["away"]["speaker"] is False
