"""The ENTSO-e prices component."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .const import CONF_COORDINATOR, CONF_VAT_VALUE, DOMAIN, CONF_API_KEY, CONF_AREA, CONF_MODIFYER, DEFAULT_MODIFYER
from .coordinator import EntsoeCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the ENTSO-e prices component from a config entry."""

    # Initialise the coordinator and save it as domain-data
    api_key = entry.options[CONF_API_KEY]
    area = entry.options[CONF_AREA]
    modifyer = entry.options.get(CONF_MODIFYER, DEFAULT_MODIFYER)
    vat = entry.options.get(CONF_VAT_VALUE, 0)
    entsoe_coordinator = EntsoeCoordinator(hass, api_key=api_key, area = area, modifyer = modifyer, VAT=vat)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_COORDINATOR: entsoe_coordinator,
    }

    # Fetch initial data, so we have data when entities subscribe and set up the platform
    await entsoe_coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
