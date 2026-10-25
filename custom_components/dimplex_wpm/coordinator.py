"""Zyklisches Lesen und Schreiben des Wärmepumpenmanagers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COIL_BLOCKS,
    CONF_COOLING_ROOM,
    CONF_SCAN_INTERVAL,
    CONF_UNIT,
    DEFAULT_COOLING_ROOM,
    DEFAULT_COOLING_SETPOINT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REG_ROOM_ADDRESS,
    REG_ROOM_SETPOINT,
    REGISTER_BLOCKS,
    ROOM_SWITCH_DELAY,
    ROOM_WRITE_INTERVAL,
)
from .modbus import DimplexModbusClient, ModbusError, ModbusExceptionResponse

_LOGGER = logging.getLogger(__name__)

ILLEGAL_ADDRESS = 2

type DimplexConfigEntry = ConfigEntry[DimplexCoordinator]


@dataclass
class DimplexData:
    """Rohwerte eines Lesezyklus."""

    registers: dict[int, int] = field(default_factory=dict)
    coils: dict[int, bool] = field(default_factory=dict)

    def signed(self, address: int) -> int | None:
        value = self.registers.get(address)
        if value is None:
            return None
        return value - 0x10000 if value >= 0x8000 else value


def software_version(data: DimplexData) -> str | None:
    """Registers 65–67, z. B. 13/3/17 → M3.17."""
    letter, number, index = (data.registers.get(a) for a in (65, 66, 67))
    if not letter or number is None or index is None:
        return None
    return f"{chr(64 + letter)}{number}.{index}"


class DimplexCoordinator(DataUpdateCoordinator[DimplexData]):
    """Hält die Verbindung, liest alle Blöcke und führt Schreibbefehle aus."""

    config_entry: DimplexConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DimplexConfigEntry) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = DimplexModbusClient(
            entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_UNIT]
        )
        self.cooling_room: int = entry.options.get(CONF_COOLING_ROOM, DEFAULT_COOLING_ROOM)
        self.cooling_setpoint: float = DEFAULT_COOLING_SETPOINT
        # Werte, die der WPM nach einem Spannungsreset vergisst (Smart Grid, Sperre extern)
        self.held: dict[int, int] = {}
        # Blöcke, die der WPM nicht am Stück liefert, und Adressen, die es nicht gibt
        self._split_blocks: set[tuple[int, int]] = set()
        self._missing_registers: set[int] = set()
        self._missing_coils: set[int] = set()
        self._unsub_room: Callable[[], None] | None = None

    @property
    def device_info(self) -> DeviceInfo:
        version = software_version(self.data) if self.data else None
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer="Dimplex",
            model="Wärmepumpenmanager",
            name="Wärmepumpe",
            sw_version=version,
            configuration_url=f"http://{self.client.host}",
        )

    async def _async_update_data(self) -> DimplexData:
        data = DimplexData()
        try:
            async with self.client.session():
                for block in REGISTER_BLOCKS:
                    data.registers.update(await self._read_block(block, coils=False))
                for block in COIL_BLOCKS:
                    data.coils.update(await self._read_block(block, coils=True))
                await self._restore_held(data)
        except ModbusError as err:
            raise UpdateFailed(str(err)) from err
        return data

    async def _read_block(self, block: tuple[int, int], *, coils: bool) -> dict:
        start, count = block
        read = self.client.read_coils if coils else self.client.read_registers
        missing = self._missing_coils if coils else self._missing_registers
        if block not in self._split_blocks:
            try:
                return dict(zip(range(start, start + count), await read(start, count)))
            except ModbusExceptionResponse as err:
                if err.code != ILLEGAL_ADDRESS:
                    raise
                _LOGGER.debug("Block %s wird einzeln gelesen", block)
                self._split_blocks.add(block)
        values = {}
        for address in range(start, start + count):
            if address in missing:
                continue
            try:
                values[address] = (await read(address, 1))[0]
            except ModbusExceptionResponse as err:
                if err.code != ILLEGAL_ADDRESS:
                    raise
                missing.add(address)
        return values

    async def _restore_held(self, data: DimplexData) -> None:
        for address, value in self.held.items():
            if address in data.registers and data.registers[address] != value:
                _LOGGER.info("Register %s nach Reset neu geschrieben (%s)", address, value)
                await self.client.write_register(address, value)
                data.registers[address] = value

    async def async_write_register(self, address: int, value: int) -> None:
        """Einzelnes Register schreiben, nur wenn sich der Wert ändert."""
        if self.data and self.data.registers.get(address) == value:
            return
        try:
            async with self.client.session():
                await self.client.write_register(address, value)
        except ModbusError as err:
            raise HomeAssistantError(f"Schreiben von Register {address} fehlgeschlagen: {err}") from err
        if self.data:
            self.data.registers[address] = value
            self.async_set_updated_data(self.data)

    async def async_hold_register(self, address: int, value: int) -> None:
        """Wert schreiben und nach einem Reset des WPM erneut setzen (0 = Hardwareeingang)."""
        if value:
            self.held[address] = value
        else:
            self.held.pop(address, None)
        await self.async_write_register(address, value)

    # Kühlanforderung über die Raumschnittstelle (Smart-RTC+)

    @callback
    def async_start_room_writer(self) -> None:
        if not self.cooling_room:
            return
        self._unsub_room = async_track_time_interval(
            self.hass,
            self._async_room_tick,
            timedelta(seconds=ROOM_WRITE_INTERVAL),
            name="Dimplex Raumsollwert",
        )
        self.config_entry.async_create_background_task(
            self.hass, self.async_write_room(), "dimplex_room_first"
        )

    @callback
    def async_stop_room_writer(self) -> None:
        if self._unsub_room:
            self._unsub_room()
            self._unsub_room = None

    async def _async_room_tick(self, _now) -> None:
        await self.async_write_room()

    async def async_write_room(self) -> None:
        """Raumadresse umschalten und nach kurzer Pause den Raumsollwert schreiben."""
        if not self.cooling_room:
            return
        try:
            async with self.client.session():
                await self.client.write_register(REG_ROOM_ADDRESS, self.cooling_room)
                await asyncio.sleep(ROOM_SWITCH_DELAY)
                await self.client.write_register(REG_ROOM_SETPOINT, round(self.cooling_setpoint * 10))
        except ModbusError as err:
            _LOGGER.warning("Raumsollwert konnte nicht geschrieben werden: %s", err)

    async def async_shutdown(self) -> None:
        self.async_stop_room_writer()
        await super().async_shutdown()
        await self.client.close()
