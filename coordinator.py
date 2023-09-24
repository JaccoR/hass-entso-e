from __future__ import annotations

import asyncio
from datetime import timedelta
from multiprocessing import AuthenticationError
from aiohttp import ClientError
import pandas as pd
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
from requests.exceptions import HTTPError

import logging

from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template, attach
from jinja2 import pass_context

from .const import DEFAULT_MODIFYER, AREA_INFO, CALCULATION_MODE


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

        attach(self.hass, self.modifyer)

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
        self.logger.debug("Fetching ENTSO-e data")
        self.logger.debug(self.area)

        time_zone = dt.now().tzinfo
        # We request data for yesterday up until tomorrow.
        yesterday = pd.Timestamp.now(tz=str(time_zone)).replace(hour=0, minute=0, second=0) - pd.Timedelta(days = 1)
        tomorrow = yesterday + pd.Timedelta(hours = 71)

        data = await self.fetch_prices(yesterday, tomorrow)
        if data is not None:
            parsed_data = self.parse_hourprices(data)
            data_all = parsed_data[-48:].to_dict()
            if parsed_data.size > 48:
                data_today = parsed_data[-48:-24].to_dict()
                data_tomorrow = parsed_data[-24:].to_dict()
            else:
                data_today = parsed_data[-24:].to_dict()
                data_tomorrow = {}

            return {
                "data": data_all,
                "dataToday": data_today,
                "dataTomorrow": data_tomorrow,
            }
        elif self.data is not None:
            newest_timestamp_today = pd.Timestamp(list(self.data["dataToday"])[-1])
            if any(self.data["dataTomorrow"]) and newest_timestamp_today < pd.Timestamp.now(newest_timestamp_today.tzinfo):
                self.data["dataToday"] = self.data["dataTomorrow"]
                self.data["dataTomorrow"] = {}
                data_list = list(self.data["data"])
                new_data_dict = {}
                if len(data_list) >= 24:
                    for hour, price in self.data["data"].items()[-24:]:
                        new_data_dict[hour] = price
                    self.data["data"] = new_data_dict

            return {
                "data": self.data["data"],
                "dataToday": self.data["dataToday"],
                "dataTomorrow": self.data["dataTomorrow"],
            }

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
        filtered_hourprices = self._filter_calculated_hourprices(self.data)
        return {
            "current_price": self.get_current_hourprice(self.data["data"]),
            "next_hour_price": self.get_next_hourprice(self.data["data"]),
            "min_price": self.get_min_price(filtered_hourprices),
            "max_price": self.get_max_price(filtered_hourprices),
            "avg_price": self.get_avg_price(filtered_hourprices),
            "time_min": self.get_min_time(filtered_hourprices),
            "time_max": self.get_max_time(filtered_hourprices),
            "prices_today": self.get_timestamped_prices(self.data["dataToday"]),
            "prices_tomorrow": self.get_timestamped_prices(self.data["dataTomorrow"]),
            "prices": self.get_timestamped_prices(self.data["data"]),
        }

    def _filter_calculated_hourprices(self, data) -> list:
        time_zone = dt.now().tzinfo
        hourprices = data["data"]
        if self.calculation_mode == CALCULATION_MODE["rotation"]:
            now = pd.Timestamp.now(tz=str(time_zone)).replace(hour=0, minute=0, second=0, microsecond=0)
            return { hour: price for hour, price in hourprices.items() if pd.to_datetime(hour) >= now and pd.to_datetime(hour) < now + timedelta(days=1) }
        elif self.calculation_mode == CALCULATION_MODE["sliding"]:
            now = pd.Timestamp.now(tz=str(time_zone)).replace(minute=0, second=0, microsecond=0)
            return { hour: price for hour, price in hourprices.items() if pd.to_datetime(hour) >= now }
        elif self.calculation_mode == CALCULATION_MODE["publish"]:
            return data["data"]

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
