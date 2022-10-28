from __future__ import annotations

import asyncio
from datetime import timedelta
import pandas as pd
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError
from requests.exceptions import HTTPError

import logging
from math import ceil


from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template, attach
from jinja2 import pass_context

from .const import DEFAULT_MODIFYER, AREA_INFO, CALCULATION_MODE, DEFAULT_WINDOWS_LENGTHS


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

    def get_double_precision_for_last_24_hours(self, hourprices, tz_info):
        # We are monitoring prices within 24 hours. If we have prices for the future
        # then start from now. If we do not have enough future data, limit window
        # to the 24 hour in the past from last known time
        last_known_time = sorted(hourprices.keys())[-1]
        time_for_24h_from_last = last_known_time - pd.Timedelta(days = 1)
        time_now = pd.Timestamp.now(tz=str(tz_info)).replace(minute = 0, second = 0, microsecond = 0)
        time_for_24h_ahead_from_now = time_now + pd.Timedelta(hours = 23)
        min_time = min(time_now, time_for_24h_from_last)
        max_time = min(time_for_24h_ahead_from_now, last_known_time)
        # Double the data to get the 30-minutes resolution
        half_hour_prices = []
        for hour, price in hourprices.items():
            if hour >= min_time and hour <= max_time:
                half_hour_prices.append({
                    "time": hour,
                    "value": price / 2,
                })
                half_hour_prices.append({
                    "time": hour + pd.Timedelta(minutes=30),
                    "value": price / 2,
                })
        return half_hour_prices

    def find_best_worst_times_for_consumption_durations(self, half_hour_prices, durations_list):
        best_prices = []
        total_price = sum(price["value"] for price in half_hour_prices)
        for duration in durations_list:
            window = ceil(duration * 2)
            if window > len(half_hour_prices):
                self.logger.warning("Not enough data for window: %f" % duration)
                best_prices.append({
                    "window": duration,
                    "time": None,
                    "total_best": None,
                    "average_best": None,
                    "average_other_time": None,
                })
                continue
            half_hour_windows = (half_hour_prices[i:i + window] for i in range(len(half_hour_prices) - window + 1))
            window_totals = tuple(sum(map(lambda x: x["value"], window_prices)) for window_prices in half_hour_windows)
            min_price = min(window_totals)
            min_price_index = window_totals.index(min_price)
            total_best_price = sum(price["value"] for price in half_hour_prices[min_price_index:min_price_index + window])
            avrg_best_price = total_best_price / duration
            total_other_price = total_price - total_best_price
            avrg_other_price = total_other_price / ((len(half_hour_prices) - window) / 2)
            best_prices.append({
                "window": duration,
                "time": half_hour_prices[min_price_index]["time"],
                "total": round(total_best_price, 5),
                "average": round(avrg_best_price, 5),
                "average_other_time": round(avrg_other_price, 5),
            })
        return best_prices

    async def _async_update_data(self) -> dict:
        """Get the latest data from ENTSO-e"""
        self.logger.debug("Fetching ENTSO-e data")
        self.logger.debug(self.area)

        time_zone = dt.now().tzinfo
        # We request data for yesterday up until tomorrow.
        yesterday = pd.Timestamp.now(tz=str(time_zone)).replace(hour=0, minute=0, second=0) - pd.Timedelta(days = 1)
        tomorrow = yesterday + pd.Timedelta(hours = 71)

        data = await self.fetch_prices(yesterday, tomorrow)

        parsed_data = self.parse_hourprices(data)
        data_all = parsed_data[-48:].to_dict()
        if parsed_data.size > 48:
            data_today = parsed_data[-48:-24].to_dict()
            data_tomorrow = parsed_data[-24:].to_dict()
        else:
            data_today = parsed_data[-24:].to_dict()
            data_tomorrow = {}

        double_precision_hourprices = self.get_double_precision_for_last_24_hours(data_all, time_zone)
        best_prices = \
            self.find_best_worst_times_for_consumption_durations(double_precision_hourprices, DEFAULT_WINDOWS_LENGTHS)

        return {
            "data": data_all,
            "dataToday": data_today,
            "dataTomorrow": data_tomorrow,
            "bestPrices": best_prices,
        }

    async def fetch_prices(self, start_date, end_date):
        try:
            # run api_update in async job
            resp = await self.hass.async_add_executor_job(
                self.api_update, start_date, end_date, self.api_key
            )

            return resp

        except NoMatchingDataError as exc:
            raise UpdateFailed("ENTSO-e prices are unavailable at the moment.") from exc
        except (HTTPError) as exc:
            if exc.response.status_code == 401:
                raise UpdateFailed("Unauthorized: Please check your API-key.") from exc
        except Exception as exc:
            raise UpdateFailed(f"Unexcpected error when fetching ENTSO-e prices: {exc}") from exc


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
            "best_prices": self.get_timestamped_windowed_prices(self.data["bestPrices"]),
            "best_start_time_for_2h": self.data["bestPrices"][DEFAULT_WINDOWS_LENGTHS.index(2.0)]["time"],
            "best_start_time_for_3h": self.data["bestPrices"][DEFAULT_WINDOWS_LENGTHS.index(3.0)]["time"],
            "best_start_time_for_4h": self.data["bestPrices"][DEFAULT_WINDOWS_LENGTHS.index(4.0)]["time"],
            "best_start_time_for_5h": self.data["bestPrices"][DEFAULT_WINDOWS_LENGTHS.index(5.0)]["time"],
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

    def get_timestamped_windowed_prices(self, hourprices):
        list = [{
            "window": item["window"],
            "time": str(item["time"]),
            "total": item["total"],
            "average": item["average"],
            "average_other_time": item["average_other_time"],
        } for item in hourprices]
        return list
