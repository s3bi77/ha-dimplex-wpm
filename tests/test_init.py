"""Tests der Integration in Home Assistant."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.dimplex_wpm.const import DOMAIN

from .conftest import FakeClient

DATA = {"host": "172.20.3.65", "port": 502, "unit": 1}


async def _setup(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, options=options or {}, unique_id="172.20.3.65:502")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow(hass: HomeAssistant, fake_client) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(DATA))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == DATA


async def test_sensors(hass: HomeAssistant, fake_client) -> None:
    await _setup(hass)
    assert hass.states.get("sensor.warmepumpe_outdoor_temperature").state == "8.5"
    assert hass.states.get("sensor.warmepumpe_flow_temperature").state == "24.8"
    assert hass.states.get("sensor.warmepumpe_status").state == "Heizen"
    assert hass.states.get("sensor.warmepumpe_status").attributes["code"] == 2
    assert hass.states.get("sensor.warmepumpe_heat_energy_heating").state == "51234"
    assert hass.states.get("sensor.warmepumpe_electric_power").state == "1300"
    assert hass.states.get("sensor.warmepumpe_software_version").state == "M3.17"
    assert hass.states.get("binary_sensor.warmepumpe_compressor_1").state == "on"
    assert hass.states.get("select.warmepumpe_operating_mode").state == "winter"
    assert hass.states.get("water_heater.warmepumpe_hot_water").attributes["temperature"] == 53
    assert hass.states.get("water_heater.warmepumpe_hot_water").state == "heat_pump"
    assert hass.states.get("number.warmepumpe_heating_curve_shift").state == "0"
    assert hass.states.get("sensor.warmepumpe_room_humidity").state == "48.0"


async def test_missing_registers_are_skipped(hass: HomeAssistant, fake_client, monkeypatch) -> None:
    original = FakeClient.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        for address in (5168, 5169, 5170, 42):
            self.registers.pop(address, None)
            self.coils.pop(address, None)

    monkeypatch.setattr(FakeClient, "__init__", init)
    await _setup(hass)
    assert hass.states.get("sensor.warmepumpe_electric_power") is None
    assert hass.states.get("sensor.warmepumpe_outdoor_temperature").state == "8.5"
    assert hass.states.get("binary_sensor.warmepumpe_compressor_1").state == "on"


async def test_writes(hass: HomeAssistant, fake_client) -> None:
    await _setup(hass)
    client = FakeClient.last
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.warmepumpe_operating_mode", "option": "cooling"}, blocking=True
    )
    await hass.services.async_call(
        "water_heater", "set_temperature", {"entity_id": "water_heater.warmepumpe_hot_water", "temperature": 50}, blocking=True
    )
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.warmepumpe_heating_curve_shift", "value": -2}, blocking=True
    )
    # Unveränderte Werte werden nicht erneut geschrieben
    await hass.services.async_call(
        "water_heater", "set_temperature", {"entity_id": "water_heater.warmepumpe_hot_water", "temperature": 50}, blocking=True
    )
    assert client.writes == [(5015, 5), (5047, 50), (5036, 17)]
    assert hass.states.get("select.warmepumpe_operating_mode").state == "cooling"


async def test_smart_grid_is_restored_after_reset(hass: HomeAssistant, fake_client) -> None:
    entry = await _setup(hass)
    client = FakeClient.last
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.warmepumpe_smart_grid", "option": "boost"}, blocking=True
    )
    assert client.registers[5167] == 11
    client.registers[5167] = 0  # Spannungsreset
    await entry.runtime_data.async_refresh()
    assert client.registers[5167] == 11
    assert client.writes[-1] == (5167, 11)
    # Zurück auf Hardwareeingang hebt das Halten auf
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.warmepumpe_smart_grid", "option": "hardware"}, blocking=True
    )
    client.registers[5167] = 0
    await entry.runtime_data.async_refresh()
    assert client.writes[-1] == (5167, 0)


async def test_cooling_room_setpoint(hass: HomeAssistant, fake_client) -> None:
    await _setup(hass, {"scan_interval": 15, "cooling_room": 60})
    client = FakeClient.last
    await hass.async_block_till_done()
    assert client.writes[:2] == [(5065, 60), (5081, 180)]
    await hass.services.async_call(
        "number", "set_value", {"entity_id": "number.warmepumpe_cooling_room_setpoint", "value": 19.5}, blocking=True
    )
    assert client.writes[-2:] == [(5065, 60), (5081, 195)]
    client.writes.clear()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=11))
    await hass.async_block_till_done()
    assert (5081, 195) in client.writes


async def test_no_cooling_room_by_default(hass: HomeAssistant, fake_client) -> None:
    await _setup(hass)
    assert hass.states.get("number.warmepumpe_cooling_room_setpoint") is None
    assert all(address != 5065 for address, _ in FakeClient.last.writes)


async def test_options_flow(hass: HomeAssistant, fake_client) -> None:
    entry = await _setup(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30, "cooling_room": 45}
    )
    assert result["errors"] == {"cooling_room": "invalid_room"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 30, "cooling_room": 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("number.warmepumpe_cooling_room_setpoint").state == "18.0"


async def test_unload(hass: HomeAssistant, fake_client) -> None:
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
