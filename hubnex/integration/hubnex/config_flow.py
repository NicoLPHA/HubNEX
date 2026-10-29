"""Config flow: found automatically from the add-on, or entered by hand."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import InvalidAuth, HubNEXClient, HubNEXError
from .const import CONF_TOKEN, CONF_URL, DOMAIN


class HubNEXConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}
        self._name = "HubNEX"

    async def _check(self, url: str, token: str) -> str | None:
        try:
            info = await HubNEXClient(self.hass, url, token).ping()
            self._name = info.get("name") or "HubNEX"  # the assistant's name (e.g. Jarvis)
        except InvalidAuth:
            return "invalid_auth"
        except HubNEXError:
            return "cannot_connect"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (error := await self._check(user_input[CONF_URL], user_input[CONF_TOKEN])):
                return self.async_create_entry(title=self._name, data=user_input)
            errors["base"] = error
        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=(user_input or {}).get(CONF_URL, "http://local-hubnex:8765")): str,
                vol.Required(CONF_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """The add-on announced itself through the Supervisor."""
        await self.async_set_unique_id(DOMAIN)
        cfg = discovery_info.config
        url = f"http://{cfg['host']}:{cfg['port']}"
        # Keep an existing entry up to date (new token or hostname after a reinstall).
        self._abort_if_unique_id_configured(updates={CONF_URL: url, CONF_TOKEN: cfg["token"]})
        self._discovered = {CONF_URL: url, CONF_TOKEN: cfg["token"]}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            if error := await self._check(self._discovered[CONF_URL], self._discovered[CONF_TOKEN]):
                return self.async_abort(reason=error)
            return self.async_create_entry(title=self._name, data=self._discovered)
        return self.async_show_form(step_id="hassio_confirm")
