from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import timedelta
from functools import cached_property

import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
from jinja2 import pass_context
from requests.exceptions import HTTPError, Timeout, ConnectionError as RequestsConnectionError

from .api_client import EntsoeClient
from .const import AREA_INFO, CALCULATION_MODE, DEFAULT_MODIFYER, ENERGY_SCALES
from .utils import get_interval_minutes, bucket_time

# depending on timezone les than 24 hours could be returned.
MIN_HOURS = 20

# Timeout settings (connect_timeout, read_timeout) in seconds
STARTUP_TIMEOUT = (5, 15)    # Faster timeout for startup - don't block HA boot
DEFAULT_TIMEOUT = (10, 30)   # Normal timeout for scheduled updates


# This class contains actually two main tasks
# 1. ENTSO: Refresh data from ENTSO on interval basis triggered by HASS every 60 minutes
# 2. ANALYSIS:  Implement some analysis on this data, like min(), max(), avg(), perc(). Updated analysis is triggered by an explicit call from a sensor
class EntsoeCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key,
        area,
        period,
        energy_scale,
        modifyer,
        calculation_mode=CALCULATION_MODE["default"],
        VAT=0,
    ) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.api_key = api_key
        self.modifyer = modifyer
        self.period = period
        self.period_minutes = get_interval_minutes(period)
        self.area = AREA_INFO[area]["code"]
        self.energy_scale = energy_scale
        self.calculation_mode = calculation_mode
        self.vat = VAT
        self.today = None
        self.calculator_last_sync = None
        self.filtered_hourprices = []
        self.lock = threading.Lock()
        self._fetch_lock = asyncio.Lock()  # Prevent concurrent API calls

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
            update_interval=timedelta(minutes=self.period_minutes),
        )

    # ENTSO: recalculate the price using the given template
    def calc_price(self, value, fake_dt=None, no_template=False) -> float:
        """Calculate price based on the users settings."""
        # Used to inject the current hour.
        # so template can be simplified using now
        if no_template:
            price = round(value / ENERGY_SCALES[self.energy_scale], 5)
            return price

        price = value / ENERGY_SCALES[self.energy_scale]
        if fake_dt is not None:

            def faker():
                def inner(*args, **kwargs):
                    return fake_dt

                return pass_context(inner)

            template_value = self.modifyer.async_render(
                now=faker(), current_price=price
            )
        else:
            template_value = self.modifyer.async_render()

        price = round(float(template_value) * (1 + self.vat), 5)

        return price

    # ENTSO: recalculate the price for each price
    def parse_hourprices(self, hourprices):
        for hour, price in hourprices.items():
            hourprices[hour] = self.calc_price(value=price, fake_dt=hour)
        return hourprices

    # ENTSO: Triggered by HA to refresh the data (interval = 60 minutes)
    async def _async_update_data(self) -> dict:
        """Get the latest data from ENTSO-e"""
        # Prevent concurrent fetches - if lock is held, skip this update
        if self._fetch_lock.locked():
            self.logger.debug("Fetch already in progress, skipping")
            return self.data
        
        async with self._fetch_lock:
            self.logger.debug("ENTSO-e DataUpdateCoordinator data update started")
            update_start = time.monotonic()

            now = dt.now()
            self.today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if self.check_update_needed(now) is False:
                self.logger.debug("Skipping api fetch. All data is already available")
                return self.data

            yesterday = self.today - timedelta(days=1)
            tomorrow_evening = yesterday + timedelta(hours=71)

            # Use faster timeout on startup (no data yet) to avoid blocking HA boot
            timeout = STARTUP_TIMEOUT if self.data is None else DEFAULT_TIMEOUT
            
            self.logger.debug(
                f"Fetching prices from {yesterday} to {tomorrow_evening} (timeout={timeout})"
            )
            data = await self.fetch_prices(yesterday, tomorrow_evening, timeout=timeout)

            if data is not None:
                parse_start = time.monotonic()
                parsed_data = self.parse_hourprices(data)
                parse_elapsed = time.monotonic() - parse_start
                self.logger.debug(f"Price parsing completed in {parse_elapsed:.2f}s")
                
                self.data = parsed_data
                total_elapsed = time.monotonic() - update_start
                self.logger.debug(
                    f"ENTSO-e update completed: {len(data)} prices in {total_elapsed:.2f}s total"
                )
                return parsed_data
            else:
                total_elapsed = time.monotonic() - update_start
                self.logger.warning(f"ENTSO-e update failed after {total_elapsed:.2f}s")

    # ENTSO: check if we need to refresh the data. If we have None, or less than 20hrs left for today, or less than 20hrs tomorrow and its after 11
    def check_update_needed(self, now):
        if self.data is None:
            return True
        if len(self.get_data_today()) < MIN_HOURS:
            return True
        if len(self.get_data_tomorrow()) < MIN_HOURS and now.hour > 11:
            return True
        return False

    # ENTSO: new prices using an async job
    async def fetch_prices(self, start_date, end_date, timeout=None):
        try:
            # run api_update in async job
            resp = await self.hass.async_add_executor_job(
                self.api_update, start_date, end_date, self.api_key, timeout
            )
            return resp

        except HTTPError as exc:
            if exc.response.status_code == 401:
                raise UpdateFailed("Unauthorized: Please check your API-key.") from exc
            self.logger.warning(f"HTTP error fetching ENTSO-e prices: {exc}")
        except (Timeout, RequestsConnectionError) as exc:
            self.logger.warning(f"Connection issue with ENTSO-e API: {exc}")
        except Exception as exc:
            self.logger.warning(f"Unexpected error fetching ENTSO-e prices: {exc}")
        
        # Handle fallback for all non-auth errors
        if self.data is not None:
            newest_timestamp = max(self.data.keys())
            if newest_timestamp > dt.now():
                self.logger.warning(
                    "Running in degraded mode (using cached data) - ENTSO-e API unavailable"
                )
            else:
                raise UpdateFailed(
                    "Cached data is stale and ENTSO-e API is unavailable"
                )
        else:
            self.logger.warning(
                "No cached data available and ENTSO-e API is unavailable - entities won't update until API recovers"
            )

    # ENTSO: the async fetch job itself
    def api_update(self, start_date, end_date, api_key, timeout=None):
        client = EntsoeClient(api_key=api_key, period=self.period)
        return client.query_day_ahead_prices(
            country_code=self.area, start=start_date, end=end_date, timeout=timeout
        )

    # ENTSO: Return the data for the given date
    def get_data(self, date):
        return {k: v for k, v in self.data.items() if k.date() == date.date()}

    # ENTSO: Return the data for today
    def get_data_today(self):
        return self.get_data(self.today)

    # ENTSO: Return the data for tomorrow
    def get_data_tomorrow(self):
        return self.get_data(self.today + timedelta(days=1))

    # ENTSO: Return the data for yesterday
    def get_data_yesterday(self):
        return self.get_data(self.today - timedelta(days=1))

    # SENSOR: Do we have data available for today
    def today_data_available(self):
        return len(self.get_data_today()) > MIN_HOURS

    @property
    def current_bucket_time(self):
        return bucket_time(dt.now(), self.period_minutes)

    # SENSOR: Get the current price
    def get_current_price(self) -> int:
        return self.data[self.current_bucket_time]

    # SENSOR: Get the next hour price
    def get_next_price(self) -> int:
        return self.data[
            self.current_bucket_time + timedelta(minutes=self.period_minutes)
        ]

    # SENSOR: Get timestamped prices of today as attribute for Average Sensor
    def get_prices_today(self):
        return self.get_timestamped_prices(self.get_data_today())

    # SENSOR: Get timestamped prices of tomorrow as attribute for Average Sensor
    def get_prices_tomorrow(self):
        return self.get_timestamped_prices(self.get_data_tomorrow())

    # SENSOR: Get timestamped prices of today & tomorrow or yesterday & today as attribute for Average Sensor
    def get_prices(self):
        if len(self.data) > 48:
            return self.get_timestamped_prices(
                {hour: price for hour, price in self.data.items() if hour >= self.today}
            )
        return self.get_timestamped_prices(
            {
                hour: price
                for hour, price in self.data.items()
                if hour >= self.today - timedelta(days=1)
            }
        )

    # SENSOR: Timestamp the prices
    def get_timestamped_prices(self, hourprices):
        list = []
        for hour, price in hourprices.items():
            str_hour = str(hour)
            list.append({"time": str_hour, "price": price})
        return list

    # --------------------------------------------------------------------------------------------------------------------------------
    # ANALYSIS: this method is called by each sensor, each complete hour, and ensures the date and filtered hourprices are in line with the current time
    # we could still optimize as not every calculator mode needs hourly updates
    async def sync_calculator(self):
        now = dt.now()
        bucket = self.current_bucket_time
        with self.lock:
            if (
                self.calculator_last_sync is None
                or self.calculator_last_sync != bucket
            ):
                self.logger.debug(
                    "The calculator needs to be synced with the current time"
                )
                if not self.data and not self._fetch_lock.locked():
                    self.logger.debug("no data available yet, fetching data")
                    await self._async_update_data()
                elif not self.data:
                    self.logger.debug("no data yet, but fetch already in progress - skipping")

                if self.today.date() != now.date():
                    self.logger.debug(
                        "new day detected: update today and filtered hourprices"
                    )
                    self.today = now.replace(hour=0, minute=0, second=0, microsecond=0)

                    # remove stale data
                    self.data = {
                        hour: price
                        for hour, price in self.data.items()
                        if hour >= self.today - timedelta(days=1)
                    }

            self.calculator_last_sync = bucket

    # ANALYSIS: filter the prices on which to apply the calculations based on the calculation_mode
    @property
    def _filtered_prices(self) -> dict:
        """
        Filter the prices based on the calculation mode.
        """
        # rotation = calculations made upon 24hrs today
        if self.calculation_mode == CALCULATION_MODE["rotation"]:
            return {
                ts: price
                for ts, price in self.data.items()
                if self.today <= ts < self.today + timedelta(days=1)
            }
        # sliding = calculations made on all data from the current bucket and beyond (future data only)
        elif self.calculation_mode == CALCULATION_MODE["sliding"]:
            return {ts: price for ts, price in self.data.items() if ts >= self.current_bucket_time}
        # publish >48 hrs of data = calculations made on all data of today and tomorrow (48 hrs)
        elif (
            self.calculation_mode == CALCULATION_MODE["publish"] and len(self.data) > 48
        ):
            return {ts: price for ts, price in self.data.items() if ts >= self.today}
        # publish <=48 hrs of data = calculations made on all data of yesterday and today (48 hrs)
        elif self.calculation_mode == CALCULATION_MODE["publish"]:
            return {
                ts: price
                for ts, price in self.data.items()
                if ts >= self.today - timedelta(days=1)
            }

        self.logger.error("Unknown calculation mode, returning empty filtered prices")
        return {}

    # ANALYSIS: Get max price in filtered period
    def get_max_price(self):
        return max(self._filtered_prices.values())

    # ANALYSIS: Get min price in filtered period
    def get_min_price(self):
        return min(self._filtered_prices.values())

    # ANALYSIS: Get timestamp of max price in filtered period
    def get_max_time(self):
        return max(self._filtered_prices, key=self._filtered_prices.get)

    # ANALYSIS: Get timestamp of min price in filtered period
    def get_min_time(self):
        return min(self._filtered_prices, key=self._filtered_prices.get)

    # ANALYSIS: Get avg price in filtered period
    def get_avg_price(self):
        return round(
            sum(self._filtered_prices.values()) / len(self._filtered_prices.values()),
            5,
        )

    # ANALYSIS: Get percentage of current price relative to maximum of filtered period
    def get_percentage_of_max(self):
        return round(self.get_current_price() / self.get_max_price() * 100, 1)

    # ANALYSIS: Get percentage of current price relative to spread (max-min) of filtered period
    def get_percentage_of_range(self):
        min = self.get_min_price()
        spread = self.get_max_price() - min
        current = self.get_current_price() - min
        return round(current / spread * 100, 1)

    # --------------------------------------------------------------------------------------------------------------------------------
    # SERVICES: returns data from the coordinator cache, or directly from ENTSO when not availble
    async def get_energy_prices(self, start_date, end_date):
        # check if we have the data already
        if (
            len(self.get_data(start_date)) > MIN_HOURS
            and len(self.get_data(end_date)) > MIN_HOURS
        ):
            self.logger.debug("return prices from coordinator cache.")
            return {
                k: v
                for k, v in self.data.items()
                if k.date() >= start_date.date() and k.date() <= end_date.date()
            }
        return self.parse_hourprices(await self.fetch_prices(start_date, end_date, timeout=DEFAULT_TIMEOUT))
