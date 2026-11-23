"""Device tracker platform for Kids Watch Tracker."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KidsWatchConfigEntry
from .entity import KidsWatchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KidsWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kids Watch trackers from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        KidsWatchTrackerEntity(coordinator, kid) for kid in coordinator.kids
    )


class KidsWatchTrackerEntity(KidsWatchEntity, TrackerEntity):
    """Representation of a Kids Watch device location."""

    _attr_name = None
    _attr_icon = "mdi:watch-variant"
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator, kid) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, kid)
        self._attr_unique_id = self.device_id

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            super().available
            and self.latitude is not None
            and self.longitude is not None
        )

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.device_data.get("latitude")

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.device_data.get("longitude")

    @property
    def location_accuracy(self) -> float:
        """Return the location accuracy of the device."""
        return self.device_data.get("accuracy") or 0
