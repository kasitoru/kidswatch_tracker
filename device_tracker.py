"""Kids Watch Tracker device tracker"""

from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any
from homeassistant.components.device_tracker import (
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt
from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_FORCE_UPDATE,
)
from .kids_watch_api import KidsWatchAPI

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kids Watch Tracker from a config entry"""
    # Create API instance
    api = KidsWatchAPI()
    # Set auth data
    api.set_auth_data(config_entry.options.get("auth_data"))
    # Get kids list
    kids = await hass.async_add_executor_job(api.get_kids)
    if kids is None:
        _LOGGER.error("Failed to get kids list: %s", api.last_error())
        return
    # Create coordinator
    coordinator = KidsWatchCoordinator(
        hass,
        api,
        config_entry.data,
        config_entry.options,
        kids,
    )
    # Create device tracker entities
    entities = []
    for kid in kids:
        entity = KidsWatchTrackerEntity(
            coordinator,
            kid,
        )
        entities.append(entity)
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "coordinator": coordinator,
        "entities": entities,
    }
    # Add entities
    async_add_entities(entities)
    # Start periodic updates
    await coordinator.async_config_entry_first_refresh()

class KidsWatchCoordinator(DataUpdateCoordinator):
    """Coordinator for Kids Watch Tracker updates"""
    
    def __init__(
        self,
        hass: HomeAssistant,
        api: KidsWatchAPI,
        config: dict,
        options: dict,
        kids: dict,
    ) -> None:
        """Initialize coordinator"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=options.get("update_interval", DEFAULT_UPDATE_INTERVAL)
            ),
        )
        self.hass = hass
        self.api = api
        self.config = config
        self.options = options
        self.kids = kids
        self.devices_data = {}
    
    async def _async_update_data(self) -> dict:
        """Fetch data from API"""
        try:
            # Update data for each kid
            for kid in self.kids:
                device_id = kid.get("device_id")
                self.devices_data.setdefault(device_id, {})
                # Get last position
                position = await self.hass.async_add_executor_job(
                    self.api.get_last_position,
                    device_id,
                )
                # Store position data
                if position:
                    kid["errors"] = 0
                    self.devices_data[device_id] = {
                        "latitude": position.get("lat"),
                        "longitude": position.get("lng"),
                        "accuracy": position.get("rad"),
                        "locate_time": position.get("locate_time"),
                        "battery": position.get("b_r"),
                        "charging": (position.get("device_state") == 8),
                        "available": True,
                    }
                else:
                    _LOGGER.warning("Failed to get position for device %s: %s", device_id, self.api.last_error())
                    kid["errors"] += 1
                # Mark the device as unavailable if there are too many errors
                if kid.get("errors", 0) >= 10:
                    self.devices_data[device_id]["available"] = False
                # Force update if enabled
                if self.options.get("force_update", DEFAULT_FORCE_UPDATE):
                    if not await self.hass.async_add_executor_job(self.api.request_current_position, device_id):
                        _LOGGER.warning("Force update failed for device %s: %s", device_id, self.api.last_error())
        except Exception as error:
            _LOGGER.warning("Failed to get position of the devices: %s", error)
        return self.devices_data

class KidsWatchTrackerEntity(TrackerEntity):
    """Representation of a Kids Watch device"""
    
    def __init__(
        self,
        coordinator: KidsWatchCoordinator,
        kid: dict,
    ) -> None:
        """Initialize the tracker"""
        self.coordinator = coordinator
        self.device_id = kid.get("device_id")
        self._name = kid.get("nickname", self.device_id)
        self._attr_icon = "mdi:watch-variant"
        self._attr_unique_id = self.device_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self._name,
            "manufacturer": "HONOR",
            "model": "Choice Kids Watch",
            "sw_version": kid.get("ver", "Unknown"),
        }
        self._attr_extra_state_attributes = self.get_device_attributes()
    
    @property
    def available(self) -> bool:
        """Return if entity is available"""
        if self.device_id in self.coordinator.devices_data:
            device_data = self.coordinator.devices_data.get(self.device_id, {})
            return device_data.get("available", False)
        return False
    
    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device"""
        if self.device_id in self.coordinator.devices_data:
            device_data = self.coordinator.devices_data.get(self.device_id, {})
            return device_data.get("latitude")
        return None
    
    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device"""
        if self.device_id in self.coordinator.devices_data:
            device_data = self.coordinator.devices_data.get(self.device_id, {})
            return device_data.get("longitude")
        return None
    
    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device"""
        if self.device_id in self.coordinator.devices_data:
            device_data = self.coordinator.devices_data.get(self.device_id, {})
            return device_data.get("accuracy")
        return None
    
    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device"""
        if self.device_id in self.coordinator.devices_data:
            device_data = self.coordinator.devices_data.get(self.device_id, {})
            return device_data.get("battery")
        return None
    
    @property
    def source_type(self) -> SourceType:
        """Return the source type"""
        return SourceType.GPS
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes"""
        attributes = dict(self._attr_extra_state_attributes)
        if self.device_id in self.coordinator.devices_data:
            attributes.update(self.get_device_attributes())
        return attributes
    
    @property
    def should_poll(self) -> bool:
        """No need to poll, coordinator notifies of updates"""
        return False
    
    @property
    def force_update(self) -> bool:
        """Force update this entity with every update from coordinator"""
        return False
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass"""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
    
    async def async_update(self) -> None:
        """Update the entity"""
        await self.coordinator.async_request_refresh()
    
    def get_device_attributes(self) -> dict:
        """Generates entity attributes from device data"""
        keys = {"locate_time", "charging"}
        attributes = self.coordinator.devices_data.get(self.device_id, {})
        attributes = {k: v for k, v in attributes.items() if k in keys}
        # Convert locate_time to human-readable format
        timestamp = attributes.get("locate_time")
        if timestamp:
            datetime = dt.as_local(dt.utc_from_timestamp(timestamp))
            attributes["locate_time"] = datetime.strftime("%d.%m.%Y %H:%M:%S")
        return attributes
