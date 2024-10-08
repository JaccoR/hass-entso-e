"""ENTSO-e current electricity and gas price information service."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    DOMAIN,
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HassJob, HomeAssistant
from homeassistant.helpers import event
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import utcnow

from .const import (
    ATTRIBUTION,
    CONF_CURRENCY,
    CONF_ENERGY_SCALE,
    CONF_ENTITY_NAME,
    DEFAULT_CURRENCY,
    DEFAULT_ENERGY_SCALE,
    DOMAIN,
)
from .coordinator import EntsoeCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntsoeEntityDescription(SensorEntityDescription):
    """Describes ENTSO-e sensor entity."""

    value_fn: Callable[[dict], StateType] = None


def sensor_descriptions(
    currency: str, energy_scale: str
) -> tuple[EntsoeEntityDescription, ...]:
    """Construct EntsoeEntityDescription."""
    return (
        EntsoeEntityDescription(
            key="current_price",
            name="Current electricity market price",
            native_unit_of_measurement=f"{currency}/{energy_scale}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_current_hourprice(),
        ),
        EntsoeEntityDescription(
            key="next_hour_price",
            name="Next hour electricity market price",
            native_unit_of_measurement=f"{currency}/{energy_scale}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_next_hourprice(),
        ),
        EntsoeEntityDescription(
            key="min_price",
            name="Lowest energy price",
            native_unit_of_measurement=f"{currency}/{energy_scale}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_min_price(),
        ),
        EntsoeEntityDescription(
            key="max_price",
            name="Highest energy price",
            native_unit_of_measurement=f"{currency}/{energy_scale}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_max_price(),
        ),
        EntsoeEntityDescription(
            key="avg_price",
            name="Average electricity price",
            native_unit_of_measurement=f"{currency}/{energy_scale}",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:currency-eur",
            suggested_display_precision=3,
            value_fn=lambda coordinator: coordinator.get_avg_price(),
        ),
        EntsoeEntityDescription(
            key="percentage_of_max",
            name="Current percentage of highest electricity price",
            native_unit_of_measurement=f"{PERCENTAGE}",
            icon="mdi:percent",
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda coordinator: coordinator.get_percentage_of_max(),
        ),
        EntsoeEntityDescription(
            key="percentage_of_range",
            name="Current percentage in electricity price range",
            native_unit_of_measurement=f"{PERCENTAGE}",
            icon="mdi:percent",
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda coordinator: coordinator.get_percentage_of_range(),
        ),
        EntsoeEntityDescription(
            key="highest_price_time_today",
            name="Time of highest price",
            device_class=SensorDeviceClass.TIMESTAMP,
            icon="mdi:clock",
            value_fn=lambda coordinator: coordinator.get_max_time(),
        ),
        EntsoeEntityDescription(
            key="lowest_price_time_today",
            name="Time of lowest price",
            device_class=SensorDeviceClass.TIMESTAMP,
            icon="mdi:clock",
            value_fn=lambda coordinator: coordinator.get_min_time(),
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ENTSO-e price sensor entries."""
    entsoe_coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    entity = {}
    for description in sensor_descriptions(
        currency=config_entry.options.get(CONF_CURRENCY, DEFAULT_CURRENCY),
        energy_scale=config_entry.options.get(CONF_ENERGY_SCALE, DEFAULT_ENERGY_SCALE),
    ):
        entity = description
        entities.append(
            EntsoeSensor(
                entsoe_coordinator, entity, config_entry.options[CONF_ENTITY_NAME]
            )
        )

    # Add an entity for each sensor type
    async_add_entities(entities, True)


class EntsoeSensor(CoordinatorEntity, RestoreSensor):
    """Representation of a ENTSO-e sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: EntsoeCoordinator,
        description: EntsoeEntityDescription,
        name: str = "",
    ) -> None:
        """Initialize the sensor."""
        self.description = description
        self.last_update_success = True

        if name not in (None, ""):
            # The Id used for addressing the entity in the ui, recorder history etc.
            self.entity_id = f"{DOMAIN}.{name}_{description.name}"
            # unique id in .storage file for ui configuration.
            self._attr_unique_id = f"entsoe.{name}_{description.key}"
            self._attr_name = f"{description.name} ({name})"
        else:
            self.entity_id = f"{DOMAIN}.{description.name}"
            self._attr_unique_id = f"entsoe.{description.key}"
            self._attr_name = f"{description.name}"

        self.entity_description: EntsoeEntityDescription = description
        self._attr_icon = description.icon
        self._attr_suggested_display_precision = (
            description.suggested_display_precision
            if description.suggested_display_precision is not None
            else 2
        )

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.entry_id}_entsoe",
                )
            },
            manufacturer="entso-e",
            model="",
            name="entso-e" + ((" (" + name + ")") if name != "" else ""),
        )

        self._update_job = HassJob(self.async_schedule_update_ha_state)
        self._unsub_update = None

        super().__init__(coordinator)

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        # _LOGGER.debug(f"update function for '{self.entity_id} called.'")

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

        # ensure the calculated data is refreshed by the changing hour
        self.coordinator.sync_calculator()

        if (
            self.coordinator.data is not None
            and self.coordinator.today_data_available()
        ):
            value: Any = None
            try:
                # _LOGGER.debug(f"current coordinator.data value: {self.coordinator.data}")
                value = self.entity_description.value_fn(self.coordinator)

                self._attr_native_value = value
                self.last_update_success = True
                _LOGGER.debug(f"updated '{self.entity_id}' to value: {value}")

            except Exception as exc:
                # No data available
                self.last_update_success = False
                _LOGGER.warning(
                    f"Unable to update entity '{self.entity_id}', value: {value} and error: {exc}, data: {self.coordinator.data}"
                )
        else:
            _LOGGER.warning(
                f"Unable to update entity '{self.entity_id}': No valid data for today available."
            )
            self.last_update_success = False

        try:
            if (
                self.description.key == "avg_price"
                and self._attr_native_value is not None
                and self.coordinator.data is not None
            ):
                self._attr_extra_state_attributes = {
                    "prices_today": self.coordinator.get_prices_today(),
                    "prices_tomorrow": self.coordinator.get_prices_tomorrow(),
                    "prices": self.coordinator.get_prices(),
                }
                _LOGGER.debug(
                    f"attributes updated: {self._attr_extra_state_attributes}"
                )
        except Exception as exc:
            _LOGGER.warning(
                f"Unable to update attributes of the average entity, error: {exc}, data: {self.coordinator.data}"
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.last_update_success
