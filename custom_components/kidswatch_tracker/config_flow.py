"""Config flow for Kids Watch Tracker integration"""

from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_FORCE_UPDATE,
    COUNTRY_CODES,
)
from .device_tracker import KidsWatchAPI

class KidsWatchTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kids Watch Tracker"""
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> KidsWatchTrackerOptionsFlow:
        """Get the options flow for this handler"""
        return KidsWatchTrackerOptionsFlow(config_entry)
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step"""
        errors = {}
        if user_input is not None:
            try:
                # Config (account data_
                config = {
                    "country_code": dict(map(reversed, COUNTRY_CODES)).get(user_input.get("country_code"), ""),
                    "phone_number": user_input.get("phone_number", ""),
                    "password": user_input.get("password", ""),
                }
                # Try to authenticate
                api = KidsWatchAPI()
                auth_data = await self.hass.async_add_executor_job(
                    api.login,
                    config.get("country_code", ""),
                    config.get("phone_number", ""),
                    config.get("password", ""),
                    f"{self.hass.config.language.lower()}_{self.hass.config.country.upper()}",
                    self.hass.config.time_zone,
                )
                if auth_data:
                    # Create unique ID for config entry
                    unique_id = f"{auth_data.get('country_code')}{auth_data.get('phone_number')}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    # Store config and options
                    options = {k: v for k, v in user_input.items() if k not in config}
                    options["auth_data"] = auth_data
                    return self.async_create_entry(title=f"Kids Watch ({unique_id})", data=config, options=options)
                else:
                    errors["base"] = api.last_error()
            except Exception as error:
                errors["base"] = str(error)
        # Build form
        data_schema = vol.Schema({
            vol.Required("country_code", default=user_input.get("country_code") if user_input else None): SelectSelector(
                SelectSelectorConfig(
                    options=[item[1] for item in COUNTRY_CODES],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="country_codes",
                )
            ),
            vol.Required("phone_number", default=user_input.get("phone_number") if user_input else None): vol.All(
                vol.Coerce(str), vol.Length(min=5, max=15)
            ),
            vol.Required("password", default=user_input.get("password") if user_input else None): str,
            vol.Optional("update_interval", default=user_input.get("update_interval", DEFAULT_UPDATE_INTERVAL) if user_input else DEFAULT_UPDATE_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=30, max=3600)
            ),
            vol.Optional("force_update", default=user_input.get("force_update", DEFAULT_FORCE_UPDATE) if user_input else DEFAULT_FORCE_UPDATE): bool,
        })
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

class KidsWatchTrackerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Kids Watch Tracker"""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow"""
        self._config_entry = config_entry
    
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options"""
        errors = {}
        config = self._config_entry.data
        options = self._config_entry.options
        if user_input is not None:
            options = {k: user_input.get(k, v) for k, v in options.items()}
            try:
                # Try to authenticate
                api = KidsWatchAPI()
                auth_data = await self.hass.async_add_executor_job(
                    api.login,
                    config.get("country_code", ""),
                    config.get("phone_number", ""),
                    config.get("password", ""),
                    options.get("auth_data", {}).get("user_lang", "en_US"),
                    options.get("auth_data", {}).get("time_zone", "UTC"),
                )
                if auth_data:
                    # Store auth data
                    options["auth_data"] = auth_data
                    # Update options
                    return self.async_create_entry(title="", data=options)
                else:
                    errors["base"] = api.last_error()
            except Exception as error:
                errors["base"] = str(error)
        # Build form
        data_schema = vol.Schema({
            vol.Optional(
                "update_interval",
                default=options.get("update_interval", DEFAULT_UPDATE_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
            vol.Optional(
                "force_update",
                default=options.get("force_update", DEFAULT_FORCE_UPDATE)
            ): bool,
        })
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
