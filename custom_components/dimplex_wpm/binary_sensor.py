"""Zustände der Ausgänge (Pumpen, Verdichter, Mischer) und Eingänge (Sperren, Smart Grid)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DimplexConfigEntry, DimplexCoordinator
from .entity import DimplexEntity


@dataclass(frozen=True, kw_only=True)
class DimplexBinaryDescription(BinarySensorEntityDescription):
    coil: int


def _out(key: str, coil: int, enabled: bool = True) -> DimplexBinaryDescription:
    return DimplexBinaryDescription(
        key=key,
        coil=coil,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=enabled,
    )


BINARY_SENSORS: tuple[DimplexBinaryDescription, ...] = (
    _out("compressor_1", 41),
    _out("compressor_2", 42, enabled=False),
    _out("primary_pump", 43),
    _out("second_heat_source", 44),
    _out("heating_pump", 45),
    _out("hot_water_pump", 46),
    _out("mixer_1_open", 47, enabled=False),
    _out("mixer_1_close", 48, enabled=False),
    _out("auxiliary_pump", 49),
    _out("flange_heater", 50),
    _out("heating_pump_2", 51, enabled=False),
    _out("mixer_2_open", 52, enabled=False),
    _out("mixer_2_close", 53, enabled=False),
    _out("pool_pump", 56, enabled=False),
    _out("heating_pump_3", 59, enabled=False),
    _out("cooling_pump", 60),
    _out("heating_pump_4", 61, enabled=False),
    _out("solar_pump", 71, enabled=False),
    _out("primary_pump_cooling", 68),
    DimplexBinaryDescription(key="thermostat_cooling", coil=66),
    DimplexBinaryDescription(key="fault_output", coil=57, device_class=BinarySensorDeviceClass.PROBLEM),
    DimplexBinaryDescription(key="smart_grid_1", coil=3, entity_registry_enabled_default=False),
    DimplexBinaryDescription(key="smart_grid_2", coil=4, entity_registry_enabled_default=False),
    DimplexBinaryDescription(key="utility_lock", coil=5),
    DimplexBinaryDescription(key="external_lock_input", coil=6),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DimplexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DimplexBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.coil in coordinator.data.coils
    )


class DimplexBinarySensor(DimplexEntity, BinarySensorEntity):
    entity_description: DimplexBinaryDescription

    def __init__(self, coordinator: DimplexCoordinator, description: DimplexBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.coils.get(self.entity_description.coil)
