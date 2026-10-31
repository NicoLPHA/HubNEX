"""The energy panel: Italian time bands and today's kWh per band."""

from datetime import datetime
from zoneinfo import ZoneInfo

from hubnex.energy import arera_band, band_until, clean_config, day_profile, easter, entities

TZ = ZoneInfo("Europe/Rome")


def at(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=TZ)


def test_arera_bands_with_saturdays_sundays_and_holidays():
    assert easter(2026).isoformat() == "2026-04-05"
    # Monday 2 November 2026
    assert [arera_band(at(2026, 11, 2, h)) for h in (6, 7, 8, 18, 19, 22, 23)] == ["F3", "F2", "F1", "F1", "F2", "F2", "F3"]
    assert arera_band(at(2026, 10, 31, 10)) == "F2" and arera_band(at(2026, 10, 31, 23)) == "F3"  # Saturday
    assert arera_band(at(2026, 11, 1, 12)) == "F3"  # Sunday (and All Saints)
    assert arera_band(at(2026, 12, 8, 12)) == "F3"  # Immacolata, a Tuesday
    assert arera_band(at(2026, 4, 6, 12)) == "F3"  # Easter Monday
    band, until = band_until(at(2026, 11, 2, 20, 30))
    assert band == "F2" and until == at(2026, 11, 2, 23)


def test_today_is_integrated_by_band():
    now = at(2026, 11, 2, 10)  # Monday: F3 until 7, F2 7-8, F1 from 8
    points = [
        ("2026-11-01T22:00:00+00:00", "500"),  # 23:00 on Sunday: holds over midnight
        ("2026-11-02T06:00:00+00:00", "2000"),  # 07:00
        ("2026-11-02T07:00:00+00:00", "1000"),  # 08:00
        ("2026-11-02T08:00:00+00:00", "unavailable"),
    ]
    out = day_profile(points, now)
    assert out["kwh"] == {"F1": 2.0, "F2": 2.0, "F3": 3.5}  # 2 h at 1 kW, 1 h at 2 kW, 7 h at 0.5 kW
    assert out["points"][0] == [0, 500.0] and out["points"][28] == [420, 2000.0] and out["now_min"] == 600
    assert len(out["points"]) == 40  # quarters of an hour so far
    assert day_profile([("2026-11-02T06:00:00+00:00", "2")], now, "kW")["kwh"]["F2"] == 2.0


def test_config_is_cleaned():
    cfg = clean_config({"views": ["bill", "nope"], "band_mode": "x", "bands": {"F1": "sensor.f1", "F9": "x"}, "contract_kw": "4,5"})
    assert cfg["views"] == ["bill"] and cfg["band_mode"] == "arera" and cfg["bands"] == {"F1": "sensor.f1"}
    assert cfg["contract_kw"] == 3.0  # not a number: back to the default
    assert entities({**cfg, "power": "sensor.w", "readouts": ["sensor.v"]}) == ["sensor.w", "sensor.f1", "sensor.v"]
