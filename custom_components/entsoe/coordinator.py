from __future__ import annotations

from requests.exceptions import HTTPError
from datetime import datetime, timedelta

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template
from jinja2 import pass_context

from .const import DEFAULT_MODIFYER, AREA_INFO, CALCULATION_MODE
from .api_client import EntsoeClient

class EntsoeCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(self, hass: HomeAssistant, api_key, area, modifyer, calculation_mode = CALCULATION_MODE["default"], VAT = 0) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.api_key = api_key
        self.modifyer = modifyer
        self.area = AREA_INFO[area]["code"]
        self.calculation_mode = calculation_mode
        self.vat = VAT
        self.today = None
        self.filtered_hourprices = []

        # Check incase the sensor was setup using config flow.
        # This blow up if the template isnt valid.
        if not isinstance(self.modifyer, Template):
            if self.modifyer in (None, ""):
                self.modifyer = DEFAULT_MODIFYER
            self.modifyer = cv.template(self.modifyer)
        # check for yaml setup.
        else:
            if self.modifyer.template in ("", None):
                self.modifyer = cv.template(DEFAULT_MODIFYER)

        logger = logging.getLogger(__name__)
        super().__init__(
            hass,
            logger,
            name="ENTSO-e coordinator",
            update_interval=timedelta(minutes=60),
        )

    def calc_price(self, value, fake_dt=None, no_template=False) -> float:
        """Calculate price based on the users settings."""
        # Used to inject the current hour.
        # so template can be simplified using now
        if no_template:
            price = round(value / 1000, 5)
            return price

        price = value / 1000
        if fake_dt is not None:

            def faker():
                def inner(*args, **kwargs):
                    return fake_dt

                return pass_context(inner)

            template_value = self.modifyer.async_render(now=faker(), current_price=price)
        else:
            template_value = self.modifyer.async_render()

        price = round(float(template_value) * (1 + self.vat), 5)

        return price

    def parse_hourprices(self, hourprices):
        for hour, price in hourprices.items():
            hourprices[hour] = self.calc_price(value=price, fake_dt=hour)
        return hourprices

    async def _async_update_data(self) -> dict:
        """Get the latest data from ENTSO-e"""
        self.logger.debug("ENTSO-e DataUpdateCoordinator data update")
        self.logger.debug(self.area)

        now = dt.now()
        self.today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.check_update_needed(now) is False:
            self.logger.debug(f"Skipping api fetch. All data is already available")
            return self.data

        yesterday = self.today - timedelta(days = 1)
        tomorrow_evening = yesterday + timedelta(hours = 71)

        self.logger.debug(f"fetching prices for start date: {yesterday} to end date: {tomorrow_evening}")
        data = await self.fetch_prices(yesterday, tomorrow_evening)
        self.logger.debug(f"received data = {data}")
        
        if data is not None:
            parsed_data = self.parse_hourprices(dict(list(data.items())[-48:]))
            self.logger.debug(f"received pricing data from entso-e for {len(data)} hours")
            self.filtered_hourprices = self._filter_calculated_hourprices(parsed_data)
            return parsed_data

    def check_update_needed(self, now):
        if self.data is None:
            return True
        if len(self.get_data_today()) != 24:
            return True
        if len(self.get_data_tomorrow()) != 24 and now.hour > 12:
            return True
        return False
    
    async def fetch_prices(self, start_date, end_date):
        try:
            # run api_update in async job
            resp = await self.hass.async_add_executor_job(
                self.api_update, start_date, end_date, self.api_key
            )
            return resp

        except (HTTPError) as exc:
            if exc.response.status_code == 401:
                raise UpdateFailed("Unauthorized: Please check your API-key.") from exc
        except Exception as exc:
            if self.data is not None:
                newest_timestamp = self.data[max(self.data.keys())]
                if(newest_timestamp) > dt.now():
                    self.logger.warning(f"Warning the integration is running in degraded mode (falling back on stored data) since fetching the latest ENTSOE-e prices failed with exception: {exc}.")
                else:
                    raise UpdateFailed(f"The latest available data is older than the current time. Therefore entities will no longer update. Error: {exc}") from exc
            else:
                self.logger.warning(f"Warning the integration doesn't have any up to date local data this means that entities won't get updated but access remains to restorable entities: {exc}.")

    def api_update(self, start_date, end_date, api_key):
        client = EntsoeClient(api_key=api_key)
        return client.query_day_ahead_prices(
            country_code=self.area, start=start_date, end=end_date
        )

    def today_data_available(self):
        return len(self.get_data_today()) == 24

    def _filter_calculated_hourprices(self, data):
        hourprices = data
        if self.calculation_mode == CALCULATION_MODE["rotation"]:
            return { hour: price for hour, price in hourprices.items() if hour >= self.today and hour < self.today + timedelta(days=1) }
        elif self.calculation_mode == CALCULATION_MODE["sliding"]:
            now = dt.now().replace(minute=0, second=0, microsecond=0)
            return { hour: price for hour, price in hourprices.items() if hour >= now }
        elif self.calculation_mode == CALCULATION_MODE["publish"]:
            return hourprices
    
    def get_prices_today(self):
        return self.get_timestamped_prices(self.get_data_today())
    
    def get_prices_tomorrow(self):
        return self.get_timestamped_prices(self.get_data_tomorrow())
    
    def get_prices(self):
        return self.get_timestamped_prices(self.data)
    
    def get_data_today(self):
        return {k: v for k, v in self.data.items() if k.date() == self.today.date()}
    
    def get_data_tomorrow(self):
        return {k: v for k, v in self.data.items() if k.date() == self.today.date() + timedelta(days=1)}

    def get_next_hourprice(self) -> int:
        return self.data[dt.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)]

    def get_current_hourprice(self) -> int:
        return self.data[dt.now().replace(minute=0, second=0, microsecond=0)]

    def get_avg_price(self):
        return round(sum(self.filtered_hourprices.values()) / len(self.filtered_hourprices.values()), 5)

    def get_max_price(self):
        return max(self.filtered_hourprices.values())

    def get_min_price(self):
        return min(self.filtered_hourprices.values())

    def get_max_time(self):
        return max(self.filtered_hourprices, key=self.filtered_hourprices.get)

    def get_min_time(self):
        return min(self.filtered_hourprices, key=self.filtered_hourprices.get)

    def get_percentage_of_max(self):
        return round(self.get_current_hourprice() / self.get_max_price() * 100, 1)

    def get_timestamped_prices(self, hourprices):
        list = []
        for hour, price in hourprices.items():
            str_hour = str(hour)
            list.append({"time": str_hour, "price": price})
        return list
