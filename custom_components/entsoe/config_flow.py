"""Config flow for Forecast.Solar integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TemplateSelector,
    TemplateSelectorConfig,
)
from homeassistant.helpers.template import Template

from .const import (
    AREA_INFO,
    CALCULATION_MODE,
    COMPONENT_TITLE,
    CONF_ADVANCED_OPTIONS,
    CONF_API_KEY,
    CONF_AREA,
    CONF_CALCULATION_MODE,
    CONF_CURRENCY,
    CONF_ENERGY_SCALE,
    CONF_ENTITY_NAME,
    CONF_MODIFYER,
    CONF_VAT_VALUE,
    DEFAULT_CURRENCY,
    DEFAULT_ENERGY_SCALE,
    DEFAULT_MODIFYER,
    DOMAIN,
    ENERGY_SCALES,
    UNIQUE_ID,
)


class EntsoeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entsoe."""

    def __init__(self):
        """Initialize ENTSO-e ConfigFlow."""
        self.area = None
        self.advanced_options = None
        self.api_key = None
        self.modifyer = None
        self.currency = None
        self.energy_scale = None
        self.name = ""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> EntsoeOptionFlowHandler:
        """Get the options flow for this handler."""
        return EntsoeOptionFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        already_configured = False

        if user_input is not None:
            self.area = user_input[CONF_AREA]
            self.advanced_options = user_input[CONF_ADVANCED_OPTIONS]
            self.api_key = user_input[CONF_API_KEY]
            self.name = user_input[CONF_ENTITY_NAME]

            if user_input[CONF_ENTITY_NAME] not in (None, ""):
                self.name = user_input[CONF_ENTITY_NAME]
            NAMED_UNIQUE_ID = self.name + UNIQUE_ID
            try:
                await self.async_set_unique_id(NAMED_UNIQUE_ID)
                self._abort_if_unique_id_configured()
            except Exception as e:
                errors["base"] = "already_configured"
                already_configured = True

            if not already_configured:
                if self.advanced_options:
                    return await self.async_step_extra()
                user_input[CONF_VAT_VALUE] = 0
                user_input[CONF_MODIFYER] = DEFAULT_MODIFYER
                user_input[CONF_CURRENCY] = DEFAULT_CURRENCY
                user_input[CONF_ENERGY_SCALE] = DEFAULT_ENERGY_SCALE
                user_input[CONF_CALCULATION_MODE] = CALCULATION_MODE["default"]

                return self.async_create_entry(
                    title=self.name or COMPONENT_TITLE,
                    data={},
                    options={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_AREA: user_input[CONF_AREA],
                        CONF_MODIFYER: user_input[CONF_MODIFYER],
                        CONF_CURRENCY: user_input[CONF_CURRENCY],
                        CONF_ENERGY_SCALE: user_input[CONF_ENERGY_SCALE],
                        CONF_ADVANCED_OPTIONS: user_input[CONF_ADVANCED_OPTIONS],
                        CONF_VAT_VALUE: user_input[CONF_VAT_VALUE],
                        CONF_ENTITY_NAME: user_input[CONF_ENTITY_NAME],
                        CONF_CALCULATION_MODE: user_input[CONF_CALCULATION_MODE],
                    },
                )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ENTITY_NAME, default=""): vol.All(
                        vol.Coerce(str)
                    ),
                    vol.Required(CONF_API_KEY): vol.All(vol.Coerce(str)),
                    vol.Required(CONF_AREA): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=country, label=info["name"])
                                for country, info in AREA_INFO.items()
                            ]
                        ),
                    ),
                    vol.Optional(CONF_ADVANCED_OPTIONS, default=False): bool,
                },
            ),
        )

    async def async_step_extra(self, user_input=None):
        """Handle VAT, template and calculation mode if requested."""
        errors = {}
        already_configured = False

        if user_input is not None:
            user_input[CONF_AREA] = self.area
            user_input[CONF_API_KEY] = self.api_key
            user_input[CONF_ENTITY_NAME] = self.name

            if user_input[CONF_ENTITY_NAME] not in (None, ""):
                self.name = user_input[CONF_ENTITY_NAME]
            NAMED_UNIQUE_ID = self.name + UNIQUE_ID
            try:
                await self.async_set_unique_id(NAMED_UNIQUE_ID)
                self._abort_if_unique_id_configured()
            except Exception as e:
                errors["base"] = "already_configured"
                already_configured = True

            template_ok = False
            if user_input[CONF_MODIFYER] in (None, ""):
                user_input[CONF_MODIFYER] = DEFAULT_MODIFYER
            else:
                # Lets try to remove the most common mistakes, this will still fail if the template
                # was writte in notepad or something like that..
                user_input[CONF_MODIFYER] = re.sub(
                    r"\s{2,}", "", user_input[CONF_MODIFYER]
                )
            if user_input[CONF_CURRENCY] in (None, ""):
                user_input[CONF_CURRENCY] = DEFAULT_CURRENCY

            if user_input[CONF_ENERGY_SCALE] in (None, ""):
                user_input[CONF_ENERGY_SCALE] = DEFAULT_ENERGY_SCALE

            template_ok = await self._valid_template(user_input[CONF_MODIFYER])

            if not already_configured:
                if template_ok:
                    if "current_price" in user_input[CONF_MODIFYER]:
                        return self.async_create_entry(
                            title=self.name or COMPONENT_TITLE,
                            data={},
                            options={
                                CONF_API_KEY: user_input[CONF_API_KEY],
                                CONF_AREA: user_input[CONF_AREA],
                                CONF_MODIFYER: user_input[CONF_MODIFYER],
                                CONF_CURRENCY: user_input[CONF_CURRENCY],
                                CONF_ENERGY_SCALE: user_input[CONF_ENERGY_SCALE],
                                CONF_VAT_VALUE: user_input[CONF_VAT_VALUE],
                                CONF_ENTITY_NAME: user_input[CONF_ENTITY_NAME],
                                CONF_CALCULATION_MODE: user_input[
                                    CONF_CALCULATION_MODE
                                ],
                            },
                        )
                    errors["base"] = "missing_current_price"
                else:
                    errors["base"] = "invalid_template"

        return self.async_show_form(
            step_id="extra",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_VAT_VALUE, default=AREA_INFO[self.area]["VAT"]
                    ): vol.All(vol.Coerce(float, "must be a number")),
                    vol.Optional(CONF_MODIFYER, default=""): TemplateSelector(
                        TemplateSelectorConfig()
                    ),
                    vol.Optional(CONF_CURRENCY, default=DEFAULT_CURRENCY): vol.All(
                        vol.Coerce(str)
                    ),
                    vol.Optional(
                        CONF_ENERGY_SCALE, default=DEFAULT_ENERGY_SCALE
                    ): vol.In(list(ENERGY_SCALES.keys())),
                    vol.Optional(
                        CONF_CALCULATION_MODE, default=CALCULATION_MODE["default"]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=value, label=key)
                                for key, value in CALCULATION_MODE.items()
                                if key != "default"
                            ]
                        ),
                    ),
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

    def __init__(self) -> None:
        """Initialize options flow."""
        self.area = None

    @property
    def config_entry(self):
        return self.hass.config_entries.async_get_entry(self.handler)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            user_input[CONF_ENTITY_NAME] = self.config_entry.options[CONF_ENTITY_NAME]
            template_ok = False
            if user_input[CONF_MODIFYER] in (None, ""):
                user_input[CONF_MODIFYER] = DEFAULT_MODIFYER
            else:
                # Lets try to remove the most common mistakes, this will still fail if the template
                # was written in notepad or something like that..
                user_input[CONF_MODIFYER] = re.sub(
                    r"\s{2,}", "", user_input[CONF_MODIFYER]
                )
            if user_input[CONF_CURRENCY] in (None, ""):
                user_input[CONF_CURRENCY] = DEFAULT_CURRENCY

            if user_input[CONF_ENERGY_SCALE] in (None, ""):
                user_input[CONF_ENERGY_SCALE] = DEFAULT_ENERGY_SCALE

            template_ok = await self._valid_template(user_input[CONF_MODIFYER])

            if template_ok:
                if "current_price" in user_input[CONF_MODIFYER]:
                    return self.async_create_entry(title="", data=user_input)
                errors["base"] = "missing_current_price"
            else:
                errors["base"] = "invalid_template"

        calculation_mode_default = self.config_entry.options.get(
            CONF_CALCULATION_MODE, CALCULATION_MODE["default"]
        )

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=self.config_entry.options[CONF_API_KEY]
                    ): vol.All(vol.Coerce(str)),
                    vol.Required(
                        CONF_AREA, default=self.config_entry.options[CONF_AREA]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=country, label=info["name"])
                                for country, info in AREA_INFO.items()
                            ]
                        ),
                    ),
                    vol.Optional(
                        CONF_VAT_VALUE,
                        default=self.config_entry.options[CONF_VAT_VALUE],
                    ): vol.All(vol.Coerce(float, "must be a number")),
                    vol.Optional(
                        CONF_MODIFYER,
                        description={"suggested_value": self.config_entry.options[CONF_MODIFYER]},
                        default=DEFAULT_MODIFYER,
                    ): TemplateSelector(TemplateSelectorConfig()),
                    vol.Optional(
                        CONF_CURRENCY,
                        default=self.config_entry.options.get(
                            CONF_CURRENCY, DEFAULT_CURRENCY
                        ),
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_ENERGY_SCALE,
                        default=self.config_entry.options.get(
                            CONF_ENERGY_SCALE, DEFAULT_ENERGY_SCALE
                        ),
                    ): vol.In(list(ENERGY_SCALES.keys())),
                    vol.Optional(
                        CONF_CALCULATION_MODE,
                        default=calculation_mode_default,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=value, label=key)
                                for key, value in CALCULATION_MODE.items()
                                if key != "default"
                            ]
                        ),
                    ),
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
