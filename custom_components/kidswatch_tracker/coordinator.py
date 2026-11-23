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
        return data

    async def _update_device(self, kid: dict[str, Any]) -> tuple[str, DeviceData]:
        """Fetch data for a single device."""
        device_id = kid["device_id"]
        previous = (self.data or {}).get(device_id, {})

        try:
            position = await self.api.get_last_position(device_id)
        except KidsWatchAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KidsWatchError as err:
            # Real API failure: keep stale data for a while (hysteresis)
            fails = self._fail_counts.get(device_id, 0) + 1
            self._fail_counts[device_id] = fails
            if fails == 1:
                _LOGGER.warning("Failed to get position for device %s: %s", device_id, err)
            elif fails == MAX_CONSECUTIVE_ERRORS:
                _LOGGER.warning(
                    "Device %s marked unavailable after %s consecutive API errors",
                    device_id, fails,
                )
            else:
                _LOGGER.debug(
                    "Failed to get position for device %s (attempt %s of %s): %s",
                    device_id, fails, MAX_CONSECUTIVE_ERRORS, err,
                )
            return device_id, {
                **previous,
                "available": bool(previous) and fails < MAX_CONSECUTIVE_ERRORS,
            }

        # API request succeeded
        self._fail_counts[device_id] = 0

        if position:
            battery = _to_float(position.get("b_r"))
            locate_time = _to_float(position.get("locate_time"))
            device_state = _to_float(position.get("device_state"))
            device_data: DeviceData = {
                "latitude": _to_float(position.get("lat")),
                "longitude": _to_float(position.get("lng")),
                "accuracy": _to_float(position.get("rad")),
                "locate_time": dt_util.utc_from_timestamp(locate_time) if locate_time else None,
                "battery": int(battery) if battery is not None else None,
                "charging": device_state == 8 if device_state is not None else None,
                "available": True,
            }
        else:
            # The cloud has no location for this device yet (e.g. the watch has
            # never reported one). This is a normal state, not an error:
            # entities stay unavailable until the first data arrives.
            _LOGGER.debug("No location data in the cloud for device %s yet", device_id)
            device_data = {**previous, "available": False}

        if self.force_update:
            try:
                await self.api.request_current_position(device_id)
            except KidsWatchAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except KidsWatchError as err:
                # Best-effort wake-up request; the watch may simply be offline
                _LOGGER.debug("Force update failed for device %s: %s", device_id, err)

        return device_id, device_data
