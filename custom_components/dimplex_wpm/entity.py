"""Gemeinsame Basis der Entitäten."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DimplexCoordinator


class DimplexEntity(CoordinatorEntity[DimplexCoordinator]):
    """Entität am Gerät "Wärmepumpe"."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DimplexCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = coordinator.device_info
