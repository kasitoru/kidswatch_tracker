"""Kids Watch Tracker integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import KidsWatchCoordinator
from .kids_watch_api import KidsWatchAPI, KidsWatchAuthError, KidsWatchError

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.BINARY_SENSOR]

KidsWatchConfigEntry = ConfigEntry[KidsWatchCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KidsWatchConfigEntry) -> bool:
    """Set up Kids Watch Tracker from a config entry."""
    api = KidsWatchAPI(async_get_clientsession(hass))
    if not api.set_auth_data(entry.data.get("auth_data")):
        raise ConfigEntryAuthFailed("Authorization data is missing")

    try:
        kids = await api.get_kids()
    except KidsWatchAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except KidsWatchError as err:
        raise ConfigEntryNotReady(str(err)) from err
    if not kids:
        raise ConfigEntryNotReady("No devices found in the Kids Watch account")

    coordinator = KidsWatchCoordinator(hass, entry, api, kids)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KidsWatchConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: KidsWatchConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
