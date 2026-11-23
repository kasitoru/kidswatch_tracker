"""Sensor platform for Kids Watch Tracker."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KidsWatchConfigEntry
from .entity import KidsWatchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KidsWatchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kids Watch sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        entity
        for kid in coordinator.kids
        for entity in (
            KidsWatchBatterySensor(coordinator, kid),
            KidsWatchLocateTimeSensor(coordinator, kid),
        )
    )


class KidsWatchBatterySensor(KidsWatchEntity, SensorEntity):
    """Battery level of the watch."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "battery"

    def __init__(self, coordinator, kid) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, kid)
        self._attr_unique_id = f"{self.device_id}_battery"

    @property
    def native_value(self) -> int | None:
        """Return the battery level."""
        return self.device_data.get("battery")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.native_value is not None


class KidsWatchLocateTimeSensor(KidsWatchEntity, SensorEntity):
    """Timestamp of the last location update reported by the cloud."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "locate_time"

    def __init__(self, coordinator, kid) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, kid)
        self._attr_unique_id = f"{self.device_id}_locate_time"

    @property
    def native_value(self) -> datetime | None:
        """Return the last location update time (UTC)."""
        return self.device_data.get("locate_time")

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.native_value is not None
