from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from homeassistant.helpers.selector import SelectOptionDict

from homeassistant.components.sensor import (
    SensorEntityDescription,
)
from homeassistant.const import (
    CURRENCY_EURO,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.helpers.typing import StateType

ATTRIBUTION = "Data provided by ENTSO-e Transparency Platform"
DOMAIN = "entsoe"
ICON = "mdi:currency-eur"
UNIQUE_ID = f"{DOMAIN}_component"
COMPONENT_TITLE = "ENTSO-e Transparency Platform"
CONF_API_KEY = "api_key"
CONF_COUNTRY = "country"
CONF_COORDINATOR = "coordinator"

TARGET_COUNTRY_OPTIONS = [
    SelectOptionDict(value='AL', label="Albania"),
    SelectOptionDict(value='AT', label="Austria"),
    SelectOptionDict(value='BE', label="Belgium"),
    SelectOptionDict(value='BA', label="Bosnia and Herz."),
    SelectOptionDict(value='BG', label="Bulgaria"),
    SelectOptionDict(value='HR', label="Croatia"),
    SelectOptionDict(value='CY', label="Cyprus"),
    SelectOptionDict(value='CZ', label="Czech Republic"),
    SelectOptionDict(value='DK', label="Denmark"),
    SelectOptionDict(value='EE', label="Estonia"),
    SelectOptionDict(value='FI', label="Finland"),
    SelectOptionDict(value='FR', label="France"),
    SelectOptionDict(value='GE', label="Georgia"),
    SelectOptionDict(value='DE', label="Germany"),
    SelectOptionDict(value='GR', label="Greece"),
    SelectOptionDict(value='HU', label="Hungary"),
    SelectOptionDict(value='IE', label="Ireland"),
    SelectOptionDict(value='IT', label="Italy"),
    SelectOptionDict(value='XK', label="Kosovo"),
    SelectOptionDict(value='LV', label="Latvia"),
    SelectOptionDict(value='LT', label="Lithuania"),
    SelectOptionDict(value='LU', label="Luxembourg"),
    SelectOptionDict(value='MT', label="Malta"),
    SelectOptionDict(value='MD', label="Moldova"),
    SelectOptionDict(value='ME', label="Montenegro"),
    SelectOptionDict(value='NL', label="Netherlands"),
    SelectOptionDict(value='MK', label="North Macedonia"),
    SelectOptionDict(value='NO', label="Norway"),
    SelectOptionDict(value='PL', label="Poland"),
    SelectOptionDict(value='PT', label="Portugal"),
    SelectOptionDict(value='RO', label="Romania"),
    SelectOptionDict(value='RS', label="Serbia"),
    SelectOptionDict(value='SK', label="Slovakia"),
    SelectOptionDict(value='SI', label="Slovenia"),
    SelectOptionDict(value='ES', label="Spain"),
    SelectOptionDict(value='SE', label="Sweden"),
    SelectOptionDict(value='CH', label="Switzerland"),
    SelectOptionDict(value='TR', label="Turkey"),
    SelectOptionDict(value='UA', label="Ukraine"),
    SelectOptionDict(value='UK', label="United Kingdom")
]


@dataclass
class EntsoeEntityDescription(SensorEntityDescription):
    """Describes ENTSO-e sensor entity."""
    value_fn: Callable[[dict], StateType] = None


SENSOR_TYPES: tuple[EntsoeEntityDescription, ...] = (
    EntsoeEntityDescription(
        key="elec_market",
        name="Current electricity market price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data['elec'] / 1000,
    ),
    EntsoeEntityDescription(
        key="elec_min",
        name="Lowest energy price today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: min(data['today_elec'])/1000,
    ),
    EntsoeEntityDescription(
        key="elec_max",
        name="Highest energy price today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: max(data['today_elec'])/1000,
    ),
    EntsoeEntityDescription(
        key="elec_avg",
        name="Average electricity price today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: round(sum(data['today_elec']) / len(data['today_elec']), 5)/1000
    )
)
