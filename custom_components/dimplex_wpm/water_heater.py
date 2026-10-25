"""Warmwasser als Wasserheizer: Isttemperatur und Solltemperatur."""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DimplexConfigEntry, DimplexCoordinator
from .entity import DimplexEntity

REG_ACTUAL = 3
REG_TARGET = 5047
REG_MIN = 5145
REG_MAX = 5048


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DimplexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if REG_TARGET in coordinator.data.registers:
        async_add_entities([DimplexHotWater(coordinator)])


class DimplexHotWater(DimplexEntity, WaterHeaterEntity):
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1

    def __init__(self, coordinator: DimplexCoordinator) -> None:
        super().__init__(coordinator, "hot_water")

    @property
    def current_temperature(self) -> float | None:
        value = self.coordinator.data.signed(REG_ACTUAL)
        return None if value is None else value / 10

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.registers.get(REG_TARGET)

    @property
    def min_temp(self) -> float:
        return self.coordinator.data.registers.get(REG_MIN) or 10

    @property
    def max_temp(self) -> float:
        return self.coordinator.data.registers.get(REG_MAX) or 85

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_write_register(REG_TARGET, round(temperature))
