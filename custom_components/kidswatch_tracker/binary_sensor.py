"""Binary sensor platform for Kids Watch Tracker."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KidsWatchConfigEntry
from .entity import KidsWatchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KidsWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kids Watch binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        KidsWatchChargingBinarySensor(coordinator, kid) for kid in coordinator.kids
    )


class KidsWatchChargingBinarySensor(KidsWatchEntity, BinarySensorEntity):
    """Charging state of the watch."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "charging"

    def __init__(self, coordinator, kid) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, kid)
        self._attr_unique_id = f"{self.device_id}_charging"

    @property
    def is_on(self) -> bool | None:
        """Return True if the watch is charging."""
        return self.device_data.get("charging")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.is_on is not None
