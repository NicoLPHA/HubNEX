"""Tests for the HubNEX Assist integration (run with pytest-homeassistant-custom-component,
with this integration available as custom_components/hubnex)."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "hubnex"
URL = "http://local-hubnex:8765"


@pytest.fixture(autouse=True)
async def setup_core(hass: HomeAssistant, enable_custom_integrations):
    # conversation needs the core integration (exposed entities) like in a real install
    assert await async_setup_component(hass, "homeassistant", {})
    yield


async def test_manual_setup_checks_the_token(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ping", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": URL, "token": "sbagliato"})
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/ping", json={"name": "Jarvis"})
    with patch("custom_components.hubnex.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": URL, "token": "giusto"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"url": URL, "token": "giusto"}


async def test_discovered_from_the_addon(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{URL}/api/ping", json={"name": "Jarvis"})
    info = HassioServiceInfo(
        config={"host": "local-hubnex", "port": 8765, "token": "interno"},
        name="HubNEX", slug="local_hubnex", uuid="1234",
    )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=info)
    assert result["step_id"] == "hassio_confirm"
    with patch("custom_components.hubnex.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"url": URL, "token": "interno"}


async def test_assist_asks_jarvis(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(f"{URL}/api/chat", json={"reply": "Luci della cucina accese, signore."})
    entry = MockConfigEntry(domain=DOMAIN, data={"url": URL, "token": "interno"}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    agent_id = er.async_get(hass).async_get_entity_id("conversation", DOMAIN, entry.entry_id)
    result = await conversation.async_converse(hass, "accendi la cucina", None, Context(), agent_id=agent_id, language="it")
    assert result.response.speech["plain"]["speech"] == "Luci della cucina accese, signore."
    method, url, payload, headers = aioclient_mock.mock_calls[-1]
    assert payload == {"text": "accendi la cucina", "channel": "assist", "voice": True}
    assert headers["Authorization"] == "Bearer interno"


async def test_assist_survives_jarvis_being_down(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(f"{URL}/api/chat", status=500)
    entry = MockConfigEntry(domain=DOMAIN, data={"url": URL, "token": "interno"}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    agent_id = er.async_get(hass).async_get_entity_id("conversation", DOMAIN, entry.entry_id)
    result = await conversation.async_converse(hass, "ciao", None, Context(), agent_id=agent_id, language="it")
    assert "non riesco a raggiungere" in result.response.speech["plain"]["speech"]
