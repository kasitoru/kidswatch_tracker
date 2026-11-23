"""Base entity for Kids Watch Tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KidsWatchCoordinator


class KidsWatchEntity(CoordinatorEntity[KidsWatchCoordinator]):
    """Common base class for all Kids Watch entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KidsWatchCoordinator,
        kid: dict[str, Any],
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device_id: str = kid["device_id"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=kid.get("nickname") or self.device_id,
            manufacturer="HONOR",
            model="Choice Kids Watch",
            sw_version=kid.get("ver"),
        )

    @property
    def device_data(self) -> dict[str, Any]:
        """Return the latest coordinator data for this device."""
        return (self.coordinator.data or {}).get(self.device_id, {})

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.device_data.get("available", False)
