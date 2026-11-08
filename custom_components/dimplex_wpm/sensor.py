"""Messwerte, Meldungen, Laufzeiten, Wärmemengen und Leistungen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FAULT_TEXT, LOCK_TEXT, SENSOR_FAULT_TEXT, STATUS_TEXT
from .coordinator import DimplexConfigEntry, DimplexCoordinator, DimplexData, software_version
from .entity import DimplexEntity


@dataclass(frozen=True, kw_only=True)
class DimplexSensorDescription(SensorEntityDescription):
    registers: tuple[int, ...]
    value: Callable[[DimplexData], float | str | None]
    raw: int | None = None  # Register, dessen Rohwert als Attribut "code" erscheint


def temperature(address: int) -> Callable[[DimplexData], float | None]:
    def _value(data: DimplexData) -> float | None:
        value = data.signed(address)
        # -99,9 °C meldet der WPM für einen fehlenden Fühler
        if value is None or value <= -999:
            return None
        return value / 10

    return _value


def scaled(address: int, factor: float) -> Callable[[DimplexData], float | None]:
    def _value(data: DimplexData) -> float | None:
        value = data.signed(address)
        return None if value is None else value * factor

    return _value


def text(address: int, table: dict[int, str]) -> Callable[[DimplexData], str | None]:
    def _value(data: DimplexData) -> str | None:
        value = data.registers.get(address)
        if value is None:
            return None
        return table.get(value, f"Unbekannt ({value})")

    return _value


def counter(low: int) -> Callable[[DimplexData], int | None]:
    """Wärmemenge aus drei Registern (Stellen 1–4, 5–8, 9–12)."""

    def _value(data: DimplexData) -> int | None:
        parts = [data.registers.get(low + i) for i in range(3)]
        if None in parts:
            return None
        return parts[2] * 100_000_000 + parts[1] * 10_000 + parts[0]

    return _value


def runtime(address: int) -> Callable[[DimplexData], int | None]:
    return lambda data: data.registers.get(address)


def _temp(key: str, address: int, enabled: bool = True) -> DimplexSensorDescription:
    return DimplexSensorDescription(
        key=key,
        registers=(address,),
        value=temperature(address),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_registry_enabled_default=enabled,
    )


def _runtime(key: str, address: int, enabled: bool = True) -> DimplexSensorDescription:
    return DimplexSensorDescription(
        key=key,
        registers=(address,),
        value=runtime(address),
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


def _energy(key: str, low: int) -> DimplexSensorDescription:
    return DimplexSensorDescription(
        key=key,
        registers=(low, low + 1, low + 2),
        value=counter(low),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )


def _power(key: str, address: int) -> DimplexSensorDescription:
    # Der WPM liefert die Leistung in 10-W-Schritten
    return DimplexSensorDescription(
        key=key,
        registers=(address,),
        value=scaled(address, 10),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    )


def _text(key: str, address: int, table: dict[int, str]) -> DimplexSensorDescription:
    return DimplexSensorDescription(
        key=key, registers=(address,), value=text(address, table), raw=address
    )


SENSORS: tuple[DimplexSensorDescription, ...] = (
    _temp("outdoor_temperature", 1),
    _temp("return_temperature", 2),
    _temp("hot_water_temperature", 3),
    _temp("flow_temperature", 5),
    # Nur bei Wärmepumpen mit elektronischem Expansionsventil vorhanden, sonst ein fester Wert
    _temp("source_inlet_temperature", 6, enabled=False),
    _temp("source_outlet_temperature", 7),
    _temp("return_target_temperature", 53),
    _temp("circuit_2_temperature", 9, enabled=False),
    _temp("circuit_2_target_temperature", 54, enabled=False),
    _temp("hot_water_target_temperature", 58, enabled=False),
    # Raumwerte nur mit busfähigem Raumfühler (RT-RTH Econ), sonst 0
    _temp("room_temperature", 11, enabled=False),
    DimplexSensorDescription(
        key="room_humidity",
        registers=(13,),
        value=scaled(13, 0.1),
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    _temp("cooling_flow_temperature", 19, enabled=False),
    _temp("cooling_return_temperature", 20, enabled=False),
    _text("status", 103, STATUS_TEXT),
    _text("lock", 104, LOCK_TEXT),
    _text("fault", 105, FAULT_TEXT),
    _text("sensor_fault", 106, SENSOR_FAULT_TEXT),
    _runtime("runtime_compressor_1", 72),
    _runtime("runtime_compressor_2", 73, enabled=False),
    _runtime("runtime_primary_pump", 74),
    _runtime("runtime_second_heat_source", 75),
    _runtime("runtime_heating_pump", 76),
    _runtime("runtime_hot_water_pump", 77),
    _runtime("runtime_flange_heater", 78),
    _runtime("runtime_pool_pump", 79, enabled=False),
    _runtime("runtime_auxiliary_pump", 71),
    _energy("heat_heating", 5096),
    _energy("heat_hot_water", 5099),
    _energy("environmental_energy", 5127),
    _power("heat_power", 5168),
    _power("electric_power", 5170),
    DimplexSensorDescription(
        key="software_version",
        registers=(65, 66, 67),
        value=software_version,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DimplexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DimplexSensor(coordinator, description)
        for description in SENSORS
        if all(r in coordinator.data.registers for r in description.registers)
    )


class DimplexSensor(DimplexEntity, SensorEntity):
    entity_description: DimplexSensorDescription

    def __init__(self, coordinator: DimplexCoordinator, description: DimplexSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        if (address := self.entity_description.raw) is None:
            return None
        if (code := self.coordinator.data.registers.get(address)) is None:
            return None
        return {"code": code}
