"""Config flow for Forecast.Solar integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import SelectSelectorConfig, SelectSelector

from .const import (
    CONF_API_KEY,
    CONF_AREA,
    DOMAIN,
    COMPONENT_TITLE,
    UNIQUE_ID,
    TARGET_AREA_OPTIONS
)


class EntsoeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Forecast.Solar."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> EntsoeOptionFlowHandler:
        """Get the options flow for this handler."""
        return EntsoeOptionFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        await self.async_set_unique_id(UNIQUE_ID)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title=COMPONENT_TITLE,
                data={},
                options={
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_AREA: user_input[CONF_AREA]
                },
            )





        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): vol.All(
                        vol.Coerce(str)),
                    vol.Required(CONF_AREA): SelectSelector(
                        SelectSelectorConfig(options=TARGET_AREA_OPTIONS),
                    )
                },
            ),
        )




class EntsoeOptionFlowHandler(OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY,
                        default=self.config_entry.options[CONF_API_KEY],
                    ): vol.All(vol.Coerce(str)),
                    vol.Required(CONF_AREA): SelectSelector(
                        SelectSelectorConfig(options=TARGET_AREA_OPTIONS),
                    ),
                }
            ),
        )
