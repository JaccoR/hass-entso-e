"""The ENTSO-e prices component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    CALCULATION_MODE,
    CONF_API_KEY,
    CONF_AREA,
    CONF_ENERGY_SCALE,
    CONF_CALCULATION_MODE,
    CONF_MODIFYER,
    CONF_VAT_VALUE,
    DEFAULT_MODIFYER,
    DEFAULT_ENERGY_SCALE,
    DOMAIN,
)
from .coordinator import EntsoeCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up ENTSO-e services."""

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the ENTSO-e prices component from a config entry."""

    # Initialise the coordinator and save it as domain-data
    api_key = entry.options[CONF_API_KEY]
    area = entry.options[CONF_AREA]
    energy_scale = entry.options.get(CONF_ENERGY_SCALE, DEFAULT_ENERGY_SCALE)
    modifyer = entry.options.get(CONF_MODIFYER, DEFAULT_MODIFYER)
    vat = entry.options.get(CONF_VAT_VALUE, 0)
    calculation_mode = entry.options.get(
        CONF_CALCULATION_MODE, CALCULATION_MODE["default"]
    )
    entsoe_coordinator = EntsoeCoordinator(
        hass,
        api_key=api_key,
        area=area,
        energy_scale=energy_scale,
        modifyer=modifyer,
        calculation_mode=calculation_mode,
        VAT=vat,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entsoe_coordinator

    # Fetch initial data, so we have data when entities subscribe and set up the platform
    await entsoe_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
