"""Einstellwerte: Warmwasser, Heizkurve, Party/Urlaub und Kühl-Raumsollwert."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
    NumberEntity,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_COOLING_SETPOINT
from .coordinator import DimplexConfigEntry, DimplexCoordinator
from .entity import DimplexEntity


@dataclass(frozen=True, kw_only=True)
class DimplexNumberDescription(NumberEntityDescription):
    register: int
    offset: int = 0  # Anzeige = Rohwert + offset


def _temp(key: str, register: int, low: float, high: float, **kwargs) -> DimplexNumberDescription:
    return DimplexNumberDescription(
        key=key,
        register=register,
        native_min_value=low,
        native_max_value=high,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        **kwargs,
    )


NUMBERS: tuple[DimplexNumberDescription, ...] = (
    _temp("hot_water_minimum", 5145, 10, 85),
    _temp("hot_water_maximum", 5048, 10, 85),
    DimplexNumberDescription(
        key="hot_water_hysteresis",
        register=5045,
        native_min_value=2,
        native_max_value=15,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    _temp("heating_curve_end", 5038, 20, 70),
    DimplexNumberDescription(
        key="heating_curve_shift",
        register=5036,
        offset=-19,
        native_min_value=-19,
        native_max_value=19,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    DimplexNumberDescription(
        key="party_hours",
        register=5016,
        native_min_value=0,
        native_max_value=72,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.HOURS,
        mode=NumberMode.BOX,
    ),
    DimplexNumberDescription(
        key="holiday_days",
        register=5017,
        native_min_value=0,
        native_max_value=150,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DimplexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        DimplexNumber(coordinator, description)
        for description in NUMBERS
        if description.register in coordinator.data.registers
    ]
    if coordinator.cooling_room:
        entities.append(CoolingSetpointNumber(coordinator))
    async_add_entities(entities)


class DimplexNumber(DimplexEntity, NumberEntity):
    entity_description: DimplexNumberDescription

    def __init__(self, coordinator: DimplexCoordinator, description: DimplexNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.registers.get(self.entity_description.register)
        return None if value is None else value + self.entity_description.offset

    async def async_set_native_value(self, value: float) -> None:
        description = self.entity_description
        await self.coordinator.async_write_register(description.register, round(value) - description.offset)


class CoolingSetpointNumber(DimplexEntity, RestoreNumber):
    """Raumsollwert, der zyklisch an die Raumschnittstelle geht, damit die Kühlung anläuft."""

    _attr_native_min_value = 10
    _attr_native_max_value = 30
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: DimplexCoordinator) -> None:
        super().__init__(coordinator, "cooling_room_setpoint")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self.coordinator.cooling_setpoint = last.native_value
        else:
            self.coordinator.cooling_setpoint = DEFAULT_COOLING_SETPOINT

    @property
    def native_value(self) -> float:
        return self.coordinator.cooling_setpoint

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.cooling_setpoint = value
        self.async_write_ha_state()
        await self.coordinator.async_write_room()

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        return {"room_address": self.coordinator.cooling_room}
