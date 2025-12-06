"""The Entso-e services."""

from __future__ import annotations

import logging
from datetime import date, datetime
from functools import partial
from typing import Final

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import EntsoeCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_CONFIG_ENTRY: Final = "config_entry"
ATTR_START: Final = "start"
ATTR_END: Final = "end"

ENERGY_SERVICE_NAME: Final = "get_energy_prices"
SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {
                "integration": DOMAIN,
            }
        ),
        vol.Optional(ATTR_START): str,
        vol.Optional(ATTR_END): str,
    }
)


def __get_date(date_input: str | None) -> date | datetime:
    """Get date."""
    if not date_input:
        return dt_util.now()

    if value := dt_util.parse_datetime(date_input):
        return value

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_date",
        translation_placeholders={
            "date": date_input,
        },
    )


def __serialize_prices(prices) -> ServiceResponse:
    """Serialize prices."""
    return {
        "prices": [
            {"timestamp": dt.isoformat(), "price": price}
            for dt, price in prices.items()
        ]
    }


def __get_coordinator(hass: HomeAssistant, call: ServiceCall) -> EntsoeCoordinator:
    """Get the coordinator from the entry."""
    entry_id: str = call.data[ATTR_CONFIG_ENTRY]
    entry: ConfigEntry | None = hass.config_entries.async_get_entry(entry_id)

    if not entry:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
            translation_placeholders={
                "config_entry": entry_id,
            },
        )
    if entry.state != ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unloaded_config_entry",
            translation_placeholders={
                "config_entry": entry.title,
            },
        )

    coordinator: EntsoeCoordinator = hass.data[DOMAIN][entry_id]
    return coordinator


async def __get_prices(
    call: ServiceCall,
    *,
    hass: HomeAssistant,
) -> ServiceResponse:
    coordinator = __get_coordinator(hass, call)

    start = __get_date(call.data.get(ATTR_START))
    end = __get_date(call.data.get(ATTR_END))

    data = await coordinator.get_energy_prices(
        start_date=start,
        end_date=end,
    )

    return __serialize_prices(data)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Entso-e services."""

    hass.services.async_register(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        partial(__get_prices, hass=hass),
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
