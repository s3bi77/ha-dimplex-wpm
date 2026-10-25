"""Betriebsmodus, Smart Grid und externe Sperre."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    EXTERNAL_LOCK_OPTIONS,
    OPERATING_MODES,
    REG_EXTERNAL_LOCK,
    REG_MODE,
    REG_SMART_GRID,
    SMART_GRID_OPTIONS,
)
from .coordinator import DimplexConfigEntry, DimplexCoordinator
from .entity import DimplexEntity


@dataclass(frozen=True, kw_only=True)
class DimplexSelectDescription(SelectEntityDescription):
    register: int
    values: dict[str, int]
    # Der WPM setzt den Wert nach einem Spannungsreset auf 0 zurück
    held: bool = False


SELECTS: tuple[DimplexSelectDescription, ...] = (
    DimplexSelectDescription(
        key="operating_mode",
        register=REG_MODE,
        values={mode: i for i, mode in enumerate(OPERATING_MODES)},
    ),
    DimplexSelectDescription(
        key="smart_grid",
        register=REG_SMART_GRID,
        values=SMART_GRID_OPTIONS,
        held=True,
    ),
    DimplexSelectDescription(
        key="external_lock",
        register=REG_EXTERNAL_LOCK,
        values=EXTERNAL_LOCK_OPTIONS,
        held=True,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DimplexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DimplexSelect(coordinator, description)
        for description in SELECTS
        if description.register in coordinator.data.registers
    )


class DimplexSelect(DimplexEntity, SelectEntity, RestoreEntity):
    entity_description: DimplexSelectDescription

    def __init__(self, coordinator: DimplexCoordinator, description: DimplexSelectDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_options = list(description.values)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        description = self.entity_description
        if not description.held or (last := await self.async_get_last_state()) is None:
            return
        if value := description.values.get(last.state):
            self.coordinator.held[description.register] = value

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data.registers.get(self.entity_description.register)
        for option, raw in self.entity_description.values.items():
            if raw == value:
                return option
        return None

    async def async_select_option(self, option: str) -> None:
        description = self.entity_description
        value = description.values[option]
        if description.held:
            await self.coordinator.async_hold_register(description.register, value)
        else:
            await self.coordinator.async_write_register(description.register, value)
