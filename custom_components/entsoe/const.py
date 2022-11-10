from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CURRENCY_EURO,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
)
from homeassistant.helpers.typing import StateType

ATTRIBUTION = "Data provided by ENTSO-e Transparency Platform"
DOMAIN = "entsoe"
ICON = "mdi:currency-eur"
UNIQUE_ID = f"{DOMAIN}_component"
COMPONENT_TITLE = "ENTSO-e Transparency Platform"

CONF_API_KEY = "api_key"
CONF_ENTITY_NAME = "name"
CONF_AREA = "area"
CONF_COORDINATOR = "coordinator"
CONF_MODIFYER = "modifyer"
CONF_ADVANCED_OPTIONS = "advanced_options"
CONF_CALCULATION_MODE = "calculation_mode"
CONF_VAT_VALUE = "VAT_value"

DEFAULT_MODIFYER = "{{current_price}}"

#default is only for internal use / backwards compatibility
CALCULATION_MODE = { "default": "publish", "rotation": "rotation", "sliding": "sliding", "publish": "publish" }

# Commented ones are not working at entsoe
AREA_INFO = {"AT":{"code":"AT", "name":"Austria", "VAT":0.21, "Currency":"EUR"},
             "BE":{"code":"BE", "name":"Belgium", "VAT":0.06, "Currency":"EUR"},
             "BG":{"code":"BG", "name":"Bulgaria", "VAT":0.21, "Currency":"EUR"},
             "HR":{"code":"HR", "name":"Croatia", "VAT":0.21, "Currency":"EUR"},
             "CZ":{"code":"CZ", "name":"Czech Republic", "VAT":0.21, "Currency":"EUR"},
             "DK_1":{"code":"DK_1", "name":"Denmark Eastern (DK1)", "VAT":0.21, "Currency":"EUR"},
             "DK_2":{"code":"DK_2", "name":"Denmark Western (DK2)", "VAT":0.21, "Currency":"EUR"},
             "EE":{"code":"EE", "name":"Estonia", "VAT":0.21, "Currency":"EUR"},
             "FI":{"code":"FI", "name":"Finland", "VAT":0.24, "Currency":"EUR"},
             "FR":{"code":"FR", "name":"France", "VAT":0.21, "Currency":"EUR"},
             "LU":{"code":"DE_LU", "name":"Luxembourg", "VAT":0.21, "Currency":"EUR"},
             "DE":{"code":"DE_LU", "name":"Germany", "VAT":0.21, "Currency":"EUR"},
             "GR":{"code":"GR", "name":"Greece", "VAT":0.21, "Currency":"EUR"},
             "HU":{"code":"HU", "name":"Hungary", "VAT":0.21, "Currency":"EUR"},
             "IT_CNOR":{"code":"IT_CNOR", "name":"Italy Centre North", "VAT":0.21, "Currency":"EUR"},
             "IT_CSUD":{"code":"IT_CSUD", "name":"Italy Centre South", "VAT":0.21, "Currency":"EUR"},
             "IT_NORD":{"code":"IT_NORD", "name":"Italy North", "VAT":0.21, "Currency":"EUR"},
             "IT_SUD":{"code":"IT_SUD", "name":"Italy South", "VAT":0.21, "Currency":"EUR"},
             "IT_SICI":{"code":"IT_SICI", "name":"Italy Sicilia", "VAT":0.21, "Currency":"EUR"},
             "IT_SARD":{"code":"IT_SARD", "name":"Italy Sardinia", "VAT":0.21, "Currency":"EUR"},
             "LV":{"code":"LV", "name":"Latvia", "VAT":0.21, "Currency":"EUR"},
             "LT":{"code":"LT", "name":"Lithuania", "VAT":0.21, "Currency":"EUR"},
             "NL":{"code":"NL", "name":"Netherlands", "VAT":0.21, "Currency":"EUR"},
             "NO_1":{"code":"NO_1", "name":"Norway Oslo (NO1)", "VAT":0.25, "Currency":"EUR"},
             "NO_2":{"code":"NO_2", "name":"Norway Kr.Sand (NO2)", "VAT":0.25, "Currency":"EUR"},
             "NO_3":{"code":"NO_3", "name":"Norway Tr.heim (NO3)", "VAT":0.25, "Currency":"EUR"},
             "NO_4":{"code":"NO_4", "name":"Norway Tromsø (NO4)", "VAT":0, "Currency":"EUR"},
             "NO_5":{"code":"NO_5", "name":"Norway Bergen (NO5)", "VAT":0.25, "Currency":"EUR"},
             "PL":{"code":"PL", "name":"Poland", "VAT":0.21, "Currency":"EUR"},
             "PT":{"code":"PT", "name":"Portugal", "VAT":0.21, "Currency":"EUR"},
             "RO":{"code":"RO", "name":"Romania", "VAT":0.21, "Currency":"EUR"},
             "RS":{"code":"RS", "name":"Serbia", "VAT":0.21, "Currency":"EUR"},
             "SK":{"code":"SK", "name":"Slovakia", "VAT":0.21, "Currency":"EUR"},
             "SI":{"code":"SI", "name":"Slovenia", "VAT":0.21, "Currency":"EUR"},
             "ES":{"code":"ES", "name":"Spain", "VAT":0.21, "Currency":"EUR"},
             "SE_1":{"code":"SE_1", "name":"Sweden Luleå (SE1)", "VAT":0.25, "Currency":"EUR"},
             "SE_2":{"code":"SE_2", "name":"Sweden Sundsvall (SE2)", "VAT":0.25, "Currency":"EUR"},
             "SE_3":{"code":"SE_3", "name":"Sweden Stockholm (SE3)", "VAT":0.25, "Currency":"EUR"},
             "SE_4":{"code":"SE_4", "name":"Sweden Malmö (SE4)", "VAT":0.25, "Currency":"EUR"},
             "CH":{"code":"CH", "name":"Switzerland", "VAT":0.21, "Currency":"EUR"},
            #  "UK":{"code":"UK", "name":"United Kingdom", "VAT":0.21, "Currency":"EUR"},
            #  "AL":{"code":"AL", "name":"Albania", "VAT":0.21, "Currency":"EUR"},
            #  "BA":{"code":"BA", "name":"Bosnia and Herz.", "VAT":0.21, "Currency":"EUR"},
            #  "CY":{"code":"CY", "name":"Cyprus", "VAT":0.21, "Currency":"EUR"},
            #  "GE":{"code":"GE", "name":"Georgia", "VAT":0.21, "Currency":"EUR"},
            #  "IE":{"code":"IE", "name":"Ireland", "VAT":0.21, "Currency":"EUR"},
            #  "XK":{"code":"XK", "name":"Kosovo", "VAT":0.21, "Currency":"EUR"},
            #  "MT":{"code":"MT", "name":"Malta", "VAT":0.21, "Currency":"EUR"},
            #  "MD":{"code":"MD", "name":"Moldova", "VAT":0.21, "Currency":"EUR"},
            #  "ME":{"code":"ME", "name":"Montenegro", "VAT":0.21, "Currency":"EUR"},
            #  "MK":{"code":"MK", "name":"North Macedonia", "VAT":0.21, "Currency":"EUR"},
            #  "TR":{"code":"TR", "name":"Turkey", "VAT":0.21, "Currency":"EUR"},
            #  "UA":{"code":"UA", "name":"Ukraine", "VAT":0.21, "Currency":"EUR"},
            }

@dataclass
class EntsoeEntityDescription(SensorEntityDescription):
    """Describes ENTSO-e sensor entity."""

    value_fn: Callable[[dict], StateType] = None


SENSOR_TYPES: tuple[EntsoeEntityDescription, ...] = (
    EntsoeEntityDescription(
        key="current_price",
        name="Current electricity market price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data["current_price"],
        state_class=SensorStateClass.MEASUREMENT
    ),
    EntsoeEntityDescription(
        key="next_hour_price",
        name="Next hour electricity market price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data["next_hour_price"],
    ),
    EntsoeEntityDescription(
        key="min_price",
        name="Lowest energy price today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data["min_price"],
    ),
    EntsoeEntityDescription(
        key="max_price",
        name="Highest energy price today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data["max_price"],
    ),
    EntsoeEntityDescription(
        key="avg_price",
        name="Average electricity price today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        value_fn=lambda data: data["avg_price"],
    ),
    EntsoeEntityDescription(
        key="percentage_of_max",
        name="Current percentage of highest electricity price today",
        native_unit_of_measurement=f"{PERCENTAGE}",
        icon="mdi:percent",
        value_fn=lambda data: round(
            data["current_price"] / data["max_price"] * 100, 1
        ),
    ),
    EntsoeEntityDescription(
        key="highest_price_time_today",
        name="Time of highest price today",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data["time_max"],
    ),
    EntsoeEntityDescription(
        key="lowest_price_time_today",
        name="Time of lowest price today",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data["time_min"],
    ),
)
