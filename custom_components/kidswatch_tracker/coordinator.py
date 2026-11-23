"""Data update coordinator for Kids Watch Tracker."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_FORCE_UPDATE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_CONSECUTIVE_ERRORS,
)
from .kids_watch_api import KidsWatchAPI, KidsWatchAuthError, KidsWatchError

_LOGGER = logging.getLogger(__name__)

DeviceData = dict[str, Any]


def _to_float(value: Any) -> float | None:
    """Safely convert an API value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class KidsWatchCoordinator(DataUpdateCoordinator[dict[str, DeviceData]]):
    """Coordinator that polls the Kids Watch cloud API in parallel."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: KidsWatchAPI,
        kids: list[dict[str, Any]],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL)
            ),
        )
        self.api = api
        self.kids = kids
        self.force_update: bool = entry.options.get("force_update", DEFAULT_FORCE_UPDATE)
        self._fail_counts: dict[str, int] = {}

    async def _async_update_data(self) -> dict[str, DeviceData]:
        """Fetch data for all devices in parallel."""
        results = await asyncio.gather(
            *(self._update_device(kid) for kid in self.kids if kid.get("device_id")),
            return_exceptions=True,
        )
        data: dict[str, DeviceData] = {}
        for result in results:
            if isinstance(result, ConfigEntryAuthFailed):
                raise result
            if isinstance(result, BaseException):
                raise UpdateFailed(f"Unexpected error: {result}") from result
            device_id, device_data = result
            data[device_id] = device_data

        # First refresh failed for every device -> let HA retry the setup
        if not self.data and not any(d["available"] for d in data.values()):
            raise UpdateFailed("No data received for any device")
        return data

    async def _update_device(self, kid: dict[str, Any]) -> tuple[str, DeviceData]:
        """Fetch data for a single device."""
        device_id = kid["device_id"]
        error: str | None = None
        try:
            position = await self.api.get_last_position(device_id)
        except KidsWatchAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KidsWatchError as err:
            position = None
            error = str(err)

        if position:
            self._fail_counts[device_id] = 0
            battery = _to_float(position.get("b_r"))
            locate_time = _to_float(position.get("locate_time"))
            device_data: DeviceData = {
                "latitude": _to_float(position.get("lat")),
                "longitude": _to_float(position.get("lng")),
                "accuracy": _to_float(position.get("rad")),
                "locate_time": dt_util.utc_from_timestamp(locate_time) if locate_time else None,
                "battery": int(battery) if battery is not None else None,
                "charging": _to_float(position.get("device_state")) == 8,
                "available": True,
            }
        else:
            fails = self._fail_counts.get(device_id, 0) + 1
            self._fail_counts[device_id] = fails
            _LOGGER.warning(
                "Failed to get position for device %s (attempt %s of %s): %s",
                device_id, fails, MAX_CONSECUTIVE_ERRORS,
                error or "location data is unavailable",
            )
            previous = (self.data or {}).get(device_id, {})
            device_data = {
                **previous,
                "available": bool(previous) and fails < MAX_CONSECUTIVE_ERRORS,
            }

        if self.force_update:
            try:
                await self.api.request_current_position(device_id)
            except KidsWatchAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except KidsWatchError as err:
                _LOGGER.warning("Force update failed for device %s: %s", device_id, err)

        return device_id, device_data
