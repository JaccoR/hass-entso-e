"""ENTSO-e current electricity and gas price information service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

import pandas as pd

from homeassistant.components.sensor import DOMAIN, RestoreSensor, SensorDeviceClass, SensorEntityDescription, SensorExtraStoredData, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
)
from homeassistant.core import HassJob, HomeAssistant
from homeassistant.helpers import event
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import utcnow
from .const import ATTRIBUTION, CONF_COORDINATOR, CONF_ENTITY_NAME, DOMAIN, ICON, DEFAULT_CURRENCY, CONF_CURRENCY
from .coordinator import EntsoeCoordinator

_LOGGER = logging.getLogger(__name__)

@dataclass
class EntsoeEntityDescription(SensorEntityDescription):
    """Describes ENTSO-e sensor entity."""

    value_fn: Callable[[dict], StateType] = None


def sensor_descriptions(currency: str) -> tuple[EntsoeEntityDescription, ...]:
    """Construct EntsoeEntityDescription."""
    return (
        EntsoeEntityDescription(
            key="current_price",
            name="Current electricity market price",
            native_unit_of_measurement=f"{currency}/{UnitOfEnergy.KILO_WATT_HOUR}",
            value_fn=lambda data: data["current_price"],
            state_class=SensorStateClass.MEASUREMENT
        ),
        EntsoeEntityDescription(
            key="next_hour_price",
            name="Next hour electricity market price",
            native_unit_of_measurement=f"{currency}/{UnitOfEnergy.KILO_WATT_HOUR}",
            value_fn=lambda data: data["next_hour_price"],
        ),
        EntsoeEntityDescription(
            key="min_price",
            name="Lowest energy price today",
            native_unit_of_measurement=f"{currency}/{UnitOfEnergy.KILO_WATT_HOUR}",
            value_fn=lambda data: data["min_price"],
        ),
        EntsoeEntityDescription(
            key="max_price",
            name="Highest energy price today",
            native_unit_of_measurement=f"{currency}/{UnitOfEnergy.KILO_WATT_HOUR}",
            value_fn=lambda data: data["max_price"],
        ),
        EntsoeEntityDescription(
            key="avg_price",
            name="Average electricity price today",
            native_unit_of_measurement=f"{currency}/{UnitOfEnergy.KILO_WATT_HOUR}",
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ENTSO-e price sensor entries."""
    entsoe_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    entities = []
    entity = {}
    for description in sensor_descriptions(currency = config_entry.options.get(CONF_CURRENCY, DEFAULT_CURRENCY)):
        entity = description
        entities.append(
            EntsoeSensor(
                entsoe_coordinator,
                entity,
                config_entry.options[CONF_ENTITY_NAME]
                ))

    # Add an entity for each sensor type
    async_add_entities(entities, True)

class EntsoeSensorExtraStoredData(SensorExtraStoredData):
    """Object to hold extra stored data."""
    _attr_extra_state_attributes: any

    def __init__(self, native_value, native_unit_of_measurement, _attr_extra_state_attributes) -> None:
        super().__init__(native_value, native_unit_of_measurement)
        self._attr_extra_state_attributes = _attr_extra_state_attributes  

    def as_dict(self) -> dict[str, any]:
        """Return a dict representation of the utility sensor data."""
        data = super().as_dict()
        data["_attr_extra_state_attributes"] = self._attr_extra_state_attributes if self._attr_extra_state_attributes is not None else None

        return data

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> EntsoeSensorExtraStoredData | None:
        """Initialize a stored sensor state from a dict."""
        extra = SensorExtraStoredData.from_dict(restored)
        if extra is None:
            return None

        _attr_extra_state_attributes: any = restored["_attr_extra_state_attributes"] if "_attr_extra_state_attributes" in restored else None

        return cls(
            extra.native_value,
            extra.native_unit_of_measurement,
            _attr_extra_state_attributes
        )  

class EntsoeSensor(CoordinatorEntity, RestoreSensor):
    """Representation of a ENTSO-e sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = ICON
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EntsoeCoordinator, description: EntsoeEntityDescription, name: str = "") -> None:
        """Initialize the sensor."""
        self.description = description

        if name not in (None, ""):
            #The Id used for addressing the entity in the ui, recorder history etc.
            self.entity_id = f"{DOMAIN}.{name}_{description.name}"
            #unique id in .storage file for ui configuration.
            self._attr_unique_id = f"entsoe.{name}_{description.key}"
            self._attr_name = f"{description.name} ({name})"
        else:
            self.entity_id = f"{DOMAIN}.{description.name}"
            self._attr_unique_id = f"entsoe.{description.key}"
            self._attr_name = f"{description.name}"

        self._attr_device_class = SensorDeviceClass.MONETARY if description.device_class is None else description.device_class
        self._attr_state_class = None if self._attr_device_class in [SensorDeviceClass.TIMESTAMP, SensorDeviceClass.MONETARY] else SensorStateClass.MEASUREMENT
        self.entity_description: EntsoeEntityDescription = description

        self._update_job = HassJob(self.async_schedule_update_ha_state)
        self._unsub_update = None

        super().__init__(coordinator)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        # if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
        #     # new introduced in 2022.04
        #     if last_sensor_data.native_value is not None:
        #         self._attr_native_value = last_sensor_data.native_value
        #     if last_sensor_data._attr_extra_state_attributes is not None:
        #         self._attr_extra_state_attributes = dict(last_sensor_data._attr_extra_state_attributes)

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug(f"update function for '{self.entity_id} called.'")
        value: Any = None
        if self.coordinator.data is not None:
            try:
                _LOGGER.debug(f"current coordinator.data value: {self.coordinator.data}")
                value = self.entity_description.value_fn(self.coordinator.processed_data())
                #Check if value if a panda timestamp and if so convert to an HA compatible format
                if isinstance(value, pd._libs.tslibs.timestamps.Timestamp):
                    value = value.to_pydatetime()

                self._attr_native_value = value
                _LOGGER.debug(f"updated '{self.entity_id}' to value: {value}")
            except Exception as exc:
                # No data available
                _LOGGER.warning(f"Unable to update entity '{self.entity_id}' due to data processing error: {value} and error: {exc} , data: {self.coordinator.data}")

        # These return pd.timestamp objects and are therefore not able to get into attributes
        invalid_keys = {"time_min", "time_max"}
        # Currency is immaterial to the entity key
        existing_entities = [type.key for type in sensor_descriptions(currency = "")]
        if self.description.key == "avg_price" and self._attr_native_value is not None:
            self._attr_extra_state_attributes = {x: self.coordinator.processed_data()[x] for x in self.coordinator.processed_data() if x not in invalid_keys and x not in existing_entities}


        # Cancel the currently scheduled event if there is any
        if self._unsub_update:
            self._unsub_update()
            self._unsub_update = None

        # Schedule the next update at exactly the next whole hour sharp
        self._unsub_update = event.async_track_point_in_utc_time(
            self.hass,
            self._update_job,
            utcnow().replace(minute=0, second=0) + timedelta(hours=1),
        )

    @property
    def extra_restore_state_data(self) -> EntsoeSensorExtraStoredData:
        """Return sensor specific state data to be restored."""
        return EntsoeSensorExtraStoredData(self._attr_native_value, None, self._attr_extra_state_attributes if hasattr(self, "_attr_extra_state_attributes") else None)

    async def async_get_last_sensor_data(self):
        """Restore Entsoe-e Sensor Extra Stored Data."""
        _LOGGER.debug("restoring sensor data")
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None

        if self.description.key == "avg_price" and self.coordinator.data is None:
            _LOGGER.debug("fallback on stored state to fill coordinator.data object")
            newest_stored_timestamp = pd.Timestamp(restored_last_extra_data.as_dict()["_attr_extra_state_attributes"].get("prices")[-1]["time"])
            current_timestamp = pd.Timestamp.now(newest_stored_timestamp.tzinfo)
            if newest_stored_timestamp < current_timestamp:
                self.coordinator.data = self.parse_attribute_data_to_coordinator_data(restored_last_extra_data.as_dict()["_attr_extra_state_attributes"])
            else:
                _LOGGER.debug("Stored state dit not contain data of today. Skipped restoring coordinator data.")

        return EntsoeSensorExtraStoredData.from_dict(
           restored_last_extra_data.as_dict()
       )

    def parse_attribute_data_to_coordinator_data(self, attributes):
        data_all = {  pd.Timestamp(item["time"]) : item["price"] for item in attributes.get("prices")[-48:] }
        if len(attributes.get("prices")) > 48:
            data_today = {  pd.Timestamp(item["time"]) : item["price"] for item in attributes.get("prices")[-48:-24] }
            data_tomorrow = {  pd.Timestamp(item["time"]) : item["price"] for item in attributes.get("prices")[-24:] }
        else:
            data_today = {  pd.Timestamp(item["time"]) : item["price"] for item in attributes.get("prices")[-24:]}
            data_tomorrow = {}
        return {
            "data": data_all,
            "dataToday": data_today,
            "dataTomorrow": data_tomorrow,            
        }
