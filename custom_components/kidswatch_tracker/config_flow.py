"""Config flow for Kids Watch Tracker integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    COUNTRY_CODE_BY_SLUG,
    COUNTRY_CODES,
    DEFAULT_FORCE_UPDATE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .kids_watch_api import KidsWatchAPI, KidsWatchConnectionError, KidsWatchError

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class KidsWatchTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kids Watch Tracker."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> KidsWatchTrackerOptionsFlow:
        """Get the options flow for this handler."""
        return KidsWatchTrackerOptionsFlow()

    async def _async_login(
        self, country_code: str, phone_number: str, password: str
    ) -> dict[str, Any]:
        """Authenticate against the cloud and return authorization data."""
        api = KidsWatchAPI(async_get_clientsession(self.hass))
        country = (self.hass.config.country or "US").upper()
        return await api.login(
            country_code,
            phone_number,
            password,
            f"{self.hass.config.language.lower()}_{country}",
            self.hass.config.time_zone,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            country_code = COUNTRY_CODE_BY_SLUG.get(user_input["country_code"], "")
            try:
                auth_data = await self._async_login(
                    country_code, user_input["phone_number"], user_input["password"]
                )
            except KidsWatchConnectionError as err:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(err)
            except KidsWatchError as err:
                errors["base"] = "auth_failed"
                placeholders["error"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error during Kids Watch login")
                errors["base"] = "unknown"
            else:
                unique_id = f"{auth_data.get('country_code')}{auth_data.get('phone_number')}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Kids Watch ({unique_id})",
                    data={
                        "country_code": country_code,
                        "phone_number": user_input["phone_number"],
                        "password": user_input["password"],
                        "auth_data": auth_data,
                    },
                    options={
                        "update_interval": user_input.get(
                            "update_interval", DEFAULT_UPDATE_INTERVAL
                        ),
                        "force_update": user_input.get("force_update", DEFAULT_FORCE_UPDATE),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required("country_code"): SelectSelector(
                    SelectSelectorConfig(
                        options=[slug for _, slug in COUNTRY_CODES],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="country_codes",
                    )
                ),
                vol.Required("phone_number"): vol.All(
                    vol.Coerce(str), vol.Length(min=5, max=15)
                ),
                vol.Required("password"): PASSWORD_SELECTOR,
                vol.Optional(
                    "update_interval", default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
                vol.Optional("force_update", default=DEFAULT_FORCE_UPDATE): bool,
            }
        )
        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthorization request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password again and refresh authorization data."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        placeholders: dict[str, str] = {
            "account": (
                f"{reauth_entry.data.get('country_code', '')}"
                f"{reauth_entry.data.get('phone_number', '')}"
            )
        }

        if user_input is not None:
            try:
                auth_data = await self._async_login(
                    reauth_entry.data["country_code"],
                    reauth_entry.data["phone_number"],
                    user_input["password"],
                )
            except KidsWatchConnectionError as err:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(err)
            except KidsWatchError as err:
                errors["base"] = "auth_failed"
                placeholders["error"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error during Kids Watch re-login")
                errors["base"] = "unknown"
            else:
                unique_id = f"{auth_data.get('country_code')}{auth_data.get('phone_number')}"
                if unique_id != reauth_entry.unique_id:
                    return self.async_abort(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        "password": user_input["password"],
                        "auth_data": auth_data,
                    },
                    options={
                        k: v for k, v in reauth_entry.options.items() if k != "auth_data"
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("password"): PASSWORD_SELECTOR}),
            errors=errors,
            description_placeholders=placeholders,
        )


class KidsWatchTrackerOptionsFlow(OptionsFlow):
    """Handle options flow for Kids Watch Tracker."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data={**self.config_entry.options, **user_input}
            )

        options = self.config_entry.options
        data_schema = vol.Schema(
            {
                vol.Optional(
                    "update_interval",
                    default=options.get("update_interval", DEFAULT_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
                vol.Optional(
                    "force_update",
                    default=options.get("force_update", DEFAULT_FORCE_UPDATE),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
