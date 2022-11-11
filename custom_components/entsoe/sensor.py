"""ENTSO-e current electricity and gas price information service."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity, DOMAIN, SensorStateClass, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HassJob, HomeAssistant
from homeassistant.helpers import event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import utcnow
from .const import ATTRIBUTION, CONF_COORDINATOR, CONF_ENTITY_NAME, DOMAIN, EntsoeEntityDescription, ICON, SENSOR_TYPES
from .coordinator import EntsoeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ENTSO-e price sensor entries."""
    entsoe_coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    entities = []
    entity = {}
    for description in SENSOR_TYPES:
        entity = description
        entities.append(
            EntsoeSensor(
                entsoe_coordinator,
                entity,
                config_entry.options[CONF_ENTITY_NAME]
                ))

    # Add an entity for each sensor type
    async_add_entities(entities, True)


class EntsoeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a ENTSO-e sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = ICON
    _attr_device_class = SensorDeviceClass.MONETARY
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

        self.entity_description: EntsoeEntityDescription = description


        self._update_job = HassJob(self.async_schedule_update_ha_state)
        self._unsub_update = None

        super().__init__(coordinator)

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        try:
            self._attr_native_value = self.entity_description.value_fn(self.coordinator.processed_data())
        except (TypeError, IndexError):
            # No data available
            self._attr_native_value = None
        # These return pd.timestamp objects and are therefore not able to get into attributes
        invalid_keys = {"time_min", "time_max", "best_start_time_for_2h", "best_start_time_for_3h", "best_start_time_for_4h", "best_start_time_for_5h"}
        existing_entities = [type.key for type in SENSOR_TYPES]
        if self.description.key == "avg_price":
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
