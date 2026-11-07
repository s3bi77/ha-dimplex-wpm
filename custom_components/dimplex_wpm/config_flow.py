"""Einrichtung über die Oberfläche: Adresse des Gateways, danach Optionen."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_COOLING_ROOM,
    CONF_SCAN_INTERVAL,
    CONF_UNIT,
    DEFAULT_COOLING_ROOM,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT,
    DOMAIN,
)
from .modbus import DimplexModbusClient, ModbusError


def _int_box(low: int, high: int) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(min=low, max=high, step=1, mode=selector.NumberSelectorMode.BOX)
    )


async def _probe(host: str, port: int, unit: int) -> None:
    """Außentemperatur lesen, um Verbindung und Unit-ID zu prüfen."""
    client = DimplexModbusClient(host, port, unit)
    try:
        async with client.session():
            await client.read_registers(1)
    finally:
        await client.close()


class DimplexConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            unit = int(user_input[CONF_UNIT])
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()
            try:
                await _probe(host, port, unit)
            except ModbusError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Wärmepumpe",
                    data={CONF_HOST: host, CONF_PORT: port, CONF_UNIT: unit},
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): _int_box(1, 65535),
                vol.Required(CONF_UNIT, default=DEFAULT_UNIT): _int_box(0, 247),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DimplexOptionsFlow()


class DimplexOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            room = int(user_input[CONF_COOLING_ROOM])
            if room and not 50 <= room <= 79:
                errors[CONF_COOLING_ROOM] = "invalid_room"
            else:
                return self.async_create_entry(
                    data={
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                        CONF_COOLING_ROOM: room,
                    }
                )
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): _int_box(5, 300),
                vol.Required(
                    CONF_COOLING_ROOM, default=options.get(CONF_COOLING_ROOM, DEFAULT_COOLING_ROOM)
                ): _int_box(0, 79),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
