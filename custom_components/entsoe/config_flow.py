"""Config flow for Forecast.Solar integration."""
from __future__ import annotations

from typing import Any
import re

import voluptuous as vol

import logging

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import SelectSelectorConfig, SelectSelector
from homeassistant.helpers.template import Template

from .const import (
    CONF_MODIFYER,
    CONF_API_KEY,
    CONF_AREA,
    DOMAIN,
    COMPONENT_TITLE,
    UNIQUE_ID,
    TARGET_AREA_OPTIONS,
    DEFAULT_TEMPLATE,
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
        errors = {}

        if user_input is not None:
            template_ok = False
            if user_input[CONF_MODIFYER] in (None, ""):
                user_input[CONF_MODIFYER] = DEFAULT_TEMPLATE
            else:
                # Lets try to remove the most common mistakes, this will still fail if the template
                # was writte in notepad or something like that..
                user_input[CONF_MODIFYER] = re.sub(
                    r"\s{2,}", "", user_input[CONF_MODIFYER]
                )

            template_ok = await self._valid_template(user_input[CONF_MODIFYER])

            if template_ok:
                if "current_price" in user_input[CONF_MODIFYER]:
                    return self.async_create_entry(
                        title=COMPONENT_TITLE,
                        data={},
                        options={
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_AREA: user_input[CONF_AREA],
                            CONF_MODIFYER: user_input[CONF_MODIFYER],
                        },
                    )
                errors["base"] = "missing_current_price"
            else:
                errors["base"] = "invalid_template"

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): vol.All(vol.Coerce(str)),
                    vol.Required(CONF_AREA): SelectSelector(
                        SelectSelectorConfig(options=TARGET_AREA_OPTIONS),
                    ),
                    vol.Optional(CONF_MODIFYER, default=""): vol.All(vol.Coerce(str)),
                },
            ),
        )

    async def _valid_template(self, user_template):
        try:
            #
            ut = Template(user_template, self.hass).async_render(
                current_price=0
            )  # Add current price as 0 as we dont know it yet..

            return True
            if isinstance(ut, float):
                return True
            else:
                return False
        except Exception as e:
            pass
        return False


class EntsoeOptionFlowHandler(OptionsFlow):
    """Handle options."""
    logger = logging.getLogger(__name__)

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            template_ok = False
            if user_input[CONF_MODIFYER] in (None, ""):
                user_input[CONF_MODIFYER] = DEFAULT_TEMPLATE
            else:
                # Lets try to remove the most common mistakes, this will still fail if the template
                # was writte in notepad or something like that..
                user_input[CONF_MODIFYER] = re.sub(
                    r"\s{2,}", "", user_input[CONF_MODIFYER]
                )

            template_ok = await self._valid_template(user_input[CONF_MODIFYER])

            if template_ok:
                if "current_price" in user_input[CONF_MODIFYER]:
                    return self.async_create_entry(title="", data=user_input)
                errors["base"] = "missing_current_price"
            else:
                errors["base"] = "invalid_template"

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY, default=self.config_entry.options[CONF_API_KEY]): vol.All(vol.Coerce(str)),
                    vol.Required(CONF_AREA, default=self.config_entry.options[CONF_AREA]): SelectSelector(
                        SelectSelectorConfig(options=TARGET_AREA_OPTIONS),
                    ),
                    vol.Optional(CONF_MODIFYER, default=self.config_entry.options[CONF_MODIFYER]): vol.All(vol.Coerce(str)),
                },
            ),
        )

    async def _valid_template(self, user_template):
        try:
            ut = Template(user_template, self.hass).async_render(
                current_price=0
            )  # Add current price as 0 as we dont know it yet..

            return True
            if isinstance(ut, float):
                return True
            else:
                return False
        except Exception as e:
            pass
        return False