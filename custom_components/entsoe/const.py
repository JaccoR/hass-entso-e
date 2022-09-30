from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

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
    selector.SelectOptionDict(value='AL', label="Albania"),
    selector.SelectOptionDict(value='AT', label="Austria"),
    selector.SelectOptionDict(value='BE', label="Belgium"),
    selector.SelectOptionDict(value='BA', label="Bosnia and Herz."),
    selector.SelectOptionDict(value='BG', label="Bulgaria"),
    selector.SelectOptionDict(value='HR', label="Croatia"),
    selector.SelectOptionDict(value='CY', label="Cyprus"),
    selector.SelectOptionDict(value='CZ', label="Czech Republic"),
    selector.SelectOptionDict(value='DK', label="Denmark"),
    selector.SelectOptionDict(value='EE', label="Estonia"),
    selector.SelectOptionDict(value='FI', label="Finland"),
    selector.SelectOptionDict(value='FR', label="France"),
    selector.SelectOptionDict(value='GE', label="Georgia"),
    selector.SelectOptionDict(value='DE', label="Germany"),
    selector.SelectOptionDict(value='GR', label="Greece"),
    selector.SelectOptionDict(value='HU', label="Hungary"),
    selector.SelectOptionDict(value='IE', label="Ireland"),
    selector.SelectOptionDict(value='IT', label="Italy"),
    selector.SelectOptionDict(value='XK', label="Kosovo"),
    selector.SelectOptionDict(value='LV', label="Latvia"),
    selector.SelectOptionDict(value='LT', label="Lithuania"),
    selector.SelectOptionDict(value='LU', label="Luxembourg"),
    selector.SelectOptionDict(value='MT', label="Malta"),
    selector.SelectOptionDict(value='MD', label="Moldova"),
    selector.SelectOptionDict(value='ME', label="Montenegro"),
    selector.SelectOptionDict(value='NL', label="Netherlands"),
    selector.SelectOptionDict(value='MK', label="North Macedonia"),
    selector.SelectOptionDict(value='NO', label="Norway"),
    selector.SelectOptionDict(value='PL', label="Poland"),
    selector.SelectOptionDict(value='PT', label="Portugal"),
    selector.SelectOptionDict(value='RO', label="Romania"),
    selector.SelectOptionDict(value='RS', label="Serbia"),
    selector.SelectOptionDict(value='SK', label="Slovakia"),
    selector.SelectOptionDict(value='SI', label="Slovenia"),
    selector.SelectOptionDict(value='ES', label="Spain"),
    selector.SelectOptionDict(value='SE', label="Sweden"),
    selector.SelectOptionDict(value='CH', label="Switzerland"),
    selector.SelectOptionDict(value='TR', label="Turkey"),
    selector.SelectOptionDict(value='UA', label="Ukraine"),
    selector.SelectOptionDict(value='UK', label="United Kingdom")
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
