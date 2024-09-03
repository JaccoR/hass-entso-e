from __future__ import annotations

from datetime import timedelta
import pandas as pd
from entsoe import EntsoePandasClient
from requests.exceptions import HTTPError
from datetime import datetime

import tzdata     # for timezone conversions in panda
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template
from jinja2 import pass_context

from .const import DEFAULT_MODIFYER, AREA_INFO, CALCULATION_MODE

class EntsoeCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""
    today = None

    def __init__(self, hass: HomeAssistant, api_key, area, modifyer, calculation_mode = CALCULATION_MODE["default"], VAT = 0) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.api_key = api_key
        self.modifyer = modifyer
        self.area = AREA_INFO[area]["code"]
        self.calculation_mode = calculation_mode
        self.vat = VAT
        self.__TIMEZONE = dt.now().tzinfo

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

        now = pd.Timestamp.now(tz=self.__TIMEZONE)
        self.today = now.normalize() 
        if self.check_update_needed(now) is False:
            self.logger.debug(f"Skipping api fetch. All data is already available")
            return self.data

        yesterday = self.today - pd.Timedelta(days = 1)
        tomorrow_evening = yesterday + pd.Timedelta(hours = 71)

        self.logger.debug(f"fetching prices for start date: {yesterday} to end date: {tomorrow_evening}")
        data = await self.fetch_prices(yesterday, tomorrow_evening)
        self.logger.debug(f"received data = {data}")

        if data is not None:
            parsed_data = self.parse_hourprices(data)
            self.logger.debug(f"received pricing data from entso-e for {data.count()} hours")
            
            return parsed_data

    def check_update_needed(self, now):
        if self.data is None:
            return True
        if self.get_data_today().count() != 24:
            return True
        if self.get_data_tomorrow().count() != 24 and now.hour > 12:
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
                newest_timestamp = pd.Timestamp(list(self.data["data"])[-1])
                if(newest_timestamp) > pd.Timestamp.now(newest_timestamp.tzinfo):
                    self.logger.warning(f"Warning the integration is running in degraded mode (falling back on stored data) since fetching the latest ENTSOE-e prices failed with exception: {exc}.")
                else:
                    self.logger.error(f"Error the latest available data is older than the current time. Therefore entities will no longer update. {exc}")
                    raise UpdateFailed(f"Unexcpected error when fetching ENTSO-e prices: {exc}") from exc
            else:
                self.logger.warning(f"Warning the integration doesn't have any up to date local data this means that entities won't get updated but access remains to restorable entities: {exc}.")

    def api_update(self, start_date, end_date, api_key):
        client = EntsoePandasClient(api_key=api_key)
        return client.query_day_ahead_prices(
            country_code=self.area, start=start_date, end=end_date
        )

    def processed_data(self):
        filtered_hourprices = self._filter_calculated_hourprices()
        today = pd.Timestamp.now(tz=self.__TIMEZONE).normalize() 

        return {
            "current_price": self.get_current_hourprice(self.data.to_dict()),
            "next_hour_price": self.get_next_hourprice(self.data.to_dict()),
            "min_price": self.get_min_price(filtered_hourprices),
            "max_price": self.get_max_price(filtered_hourprices),
            "avg_price": self.get_avg_price(filtered_hourprices),
            "time_min": self.get_min_time(filtered_hourprices),
            "time_max": self.get_max_time(filtered_hourprices),
            "prices_today": self.get_timestamped_prices(self.get_data_today().to_dict()),
            "prices_tomorrow": self.get_timestamped_prices(self.get_data_tomorrow().to_dict()),
            "prices": self.get_timestamped_prices(self.data.to_dict()),
        }
    
    def get_data_today(self):
        return self.data[self.today: self.today + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]
    
    def get_data_tomorrow(self):
        return self.data[self.today + pd.Timedelta(days=1) : self.today + pd.Timedelta(days=1) + pd.Timedelta(hours=23)]

    def _filter_calculated_hourprices(self) -> list:
        time_zone = dt.now().tzinfo
        hourprices = self.data.to_dict()
        if self.calculation_mode == CALCULATION_MODE["rotation"]:
            now = pd.Timestamp.now(tz=str(time_zone)).normalize()
            return { hour: price for hour, price in hourprices.items() if pd.to_datetime(hour) >= now and pd.to_datetime(hour) < now + timedelta(days=1) }
        elif self.calculation_mode == CALCULATION_MODE["sliding"]:
            now = pd.Timestamp.now(tz=str(time_zone)).normalize()
            return { hour: price for hour, price in hourprices.items() if pd.to_datetime(hour) >= now }
        elif self.calculation_mode == CALCULATION_MODE["publish"]:
            return hourprices

    def get_next_hourprice(self, hourprices) -> int:
        for hour, price in hourprices.items():
            if hour - timedelta(hours=1) <= dt.utcnow() < hour:
                return price

    def get_current_hourprice(self, hourprices) -> int:
        for hour, price in hourprices.items():
            if hour <= dt.utcnow() < hour + timedelta(hours=1):
                return price

    def get_hourprices(self, hourprices) -> list:
        return [a for a in hourprices.values()]

    def get_avg_price(self, hourprices):
        return round(sum(hourprices.values()) / len(hourprices.values()), 5)

    def get_max_price(self, hourprices):
        return max(hourprices.values())

    def get_min_price(self, hourprices):
        return min(hourprices.values())

    def get_max_time(self, hourprices):
        return max(hourprices, key=hourprices.get)

    def get_min_time(self, hourprices):
        return min(hourprices, key=hourprices.get)

    def get_timestamped_prices(self, hourprices):
        list = []
        for hour, price in hourprices.items():
            str_hour = str(hour)
            list.append({"time": str_hour, "price": price})
        return list
