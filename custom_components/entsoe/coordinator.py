from __future__ import annotations

import logging
from datetime import datetime, timedelta

import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
from jinja2 import pass_context
from requests.exceptions import HTTPError

from .api_client import EntsoeClient
from .const import AREA_INFO, ANALYSIS_WINDOW, DEFAULT_MODIFYER, ENERGY_SCALES

# depending on timezone less than 24 hours could be returned.
# TODO: is this still a valid minimum now that we fill missing hours in the api_client?
MIN_HOURS = 20

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
        energy_scale,
        modifyer,
        analysis_window=ANALYSIS_WINDOW["default"],
        VAT=0,
    ) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.api_key = api_key
        self.modifyer = modifyer
        self.area = AREA_INFO[area]["code"]
        self.energy_scale = energy_scale
        self.analysis_window = analysis_window
        self.vat = VAT
        self.today = None
        self.last_analysis = None
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
        self.logger.debug("ENTSO-e DataUpdateCoordinator data update")
        self.logger.debug(self.area)

        now = dt.now()
        self.today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.check_update_needed(now) is False:
            self.logger.debug(f"Skipping api fetch. All data is already available")
            return self.data

        yesterday = self.today - timedelta(days=1)
        tomorrow_evening = yesterday + timedelta(hours=71)

        self.logger.debug(
            f"fetching prices for start date: {yesterday} to end date: {tomorrow_evening}"
        )
        data = await self.fetch_prices(yesterday, tomorrow_evening)
        self.logger.debug(f"received data = {data}")

        if data is not None:
            parsed_data = self.parse_hourprices(data)
            self.logger.debug(
                f"received pricing data from entso-e for {len(data)} hours"
            )
            self.data = parsed_data
            self.filtered_hourprices = self._filter_analysis_window(parsed_data)
            return parsed_data

    # ENTSO: check if we need to refresh the data. If we have None, or less than 20hrs for today, or less than 20hrs tomorrow and its after 11
    def check_update_needed(self, now):
        if self.data is None:
            return True
        if len(self.get_data_today()) < MIN_HOURS:
            return True
        if len(self.get_data_tomorrow()) < MIN_HOURS and now.hour > 11:
            return True
        return False

    # ENTSO: fetch new prices using an async job
    async def fetch_prices(self, start_date, end_date):
        try:
            # run api_update in async job
            resp = await self.hass.async_add_executor_job(
                self.api_update, start_date, end_date, self.api_key
            )
            return resp

        except HTTPError as exc:
            if exc.response.status_code == 401:
                raise UpdateFailed("Unauthorized: Please check your API-key.") from exc
        except Exception as exc:
            if self.data is not None:
                newest_timestamp = self.data[max(self.data.keys())]
                if (newest_timestamp) > dt.now():
                    self.logger.warning(
                        f"Warning the integration is running in degraded mode (falling back on stored data) since fetching the latest ENTSOE-e prices failed with exception: {exc}."
                    )
                else:
                    raise UpdateFailed(
                        f"The latest available data is older than the current time. Therefore entities will no longer update. Error: {exc}"
                    ) from exc
            else:
                self.logger.warning(
                    f"Warning the integration doesn't have any up to date local data this means that entities won't get updated but access remains to restorable entities: {exc}."
                )

    # ENTSO: the async fetch job itself
    def api_update(self, start_date, end_date, api_key):
        client = EntsoeClient(api_key=api_key)
        return client.query_day_ahead_prices(
            country_code=self.area, start=start_date, end=end_date
        )
    
    # --------------------------------------------------------------------------------------------------------------------------------
    # ENTSO: Return the data for the given date
    def get_data(self, date):
        return {k: v for k, v in self.data.items() if k.date() == date.date()}

    # ENTSO: Return a valid 48hrs dataset as in some occassions we only have 48hrs of data
    # -> fetch starts after 11:00 after which we loose the data of the day before yesterday
    # -> until we obtain tomorrow's data we only have 48hrs of data (of yesterday and today)
    # -> after ~13:00 we will be back to 72hrs of cached data
    def get_48hrs_data(self):
        start = self.today                  # default we return 48hrs starting today
        if len(self.data) <= 48:
            start -= timedelta(days=1)      # unless we dont have tomorrows data, then we start yesterday

        return {hour: price for hour, price in self.data.items() if hour >= start}
        
    # ENTSO: Return the data for today
    def get_data_today(self):
        return self.get_data(self.today)

    # ENTSO: Return the data for tomorrow
    def get_data_tomorrow(self):
        return self.get_data(self.today + timedelta(days=1))

    # ENTSO: Return the data for yesterday
    def get_data_yesterday(self):
        return self.get_data(self.today - timedelta(days=1))

    # --------------------------------------------------------------------------------------------------------------------------------
    # SENSOR: Get the current price
    def get_current_hourprice(self) -> int:
        return self.data[dt.now().replace(minute=0, second=0, microsecond=0)]

    # SENSOR: Get the next hour price
    def get_next_hourprice(self) -> int:
        return self.data[
            dt.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        ]

    # SENSOR: Get timestamped prices of today as attribute for Average Sensor
    def get_prices_today(self):
        return self.get_timestamped_prices(self.get_data_today())

    # SENSOR: Get timestamped prices of tomorrow as attribute for Average Sensor
    def get_prices_tomorrow(self):
        return self.get_timestamped_prices(self.get_data_tomorrow())

    # SENSOR: Get timestamped 48hrs prices as attribute for Average Sensor
    def get_prices(self):
        return self.get_timestamped_prices(self.get_48hrs_data())

    # SENSOR: Helper to timestamp the prices
    def get_timestamped_prices(self, hourprices):
        list = []
        for hour, price in hourprices.items():
            str_hour = str(hour)
            list.append({"time": str_hour, "price": price})
        return list

    # --------------------------------------------------------------------------------------------------------------------------------
    # ANALYSIS: this method is called by each sensor, each complete hour, and ensures the date and filtered hourprices are in line with the current time
    # we could still optimize as not every calculator mode needs hourly updates
    def refresh_analysis(self):
        now = dt.now()
        if (self.last_analysis is None 
            or self.last_analysis.hour != now.hour
        ):
            self.logger.debug(
                f"The analysis window needs to be updated to the current time"
            )
            if self.today.date() != now.date():
                self.logger.debug(
                    f"new day detected: update today and filtered hourprices"
                )
                self.today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self.filtered_hourprices = self._filter_analysis_window(self.data)

        self.last_analysis  = now

    # ANALYSIS: filter the hourprices on which to apply the analysis 
    def _filter_analysis_window(self, data):
        last_hour = dt.now().replace(minute=0, second=0, microsecond=0)

        if self.analysis_window == ANALYSIS_WINDOW["today"]:
            self.logger.debug(f"Filter dataset for prices today -> refresh each day")
            start   = self.today
            end     = start + timedelta(days=1)

        elif self.analysis_window == ANALYSIS_WINDOW["sliding-24"]:
            start   = last_hour - timedelta(hours=12)
            end     = start     + timedelta(hours=24)
            self.logger.debug(f"Filter dataset to surrounding 24hrs {start} - {end} -> refresh each hour")
        
        elif self.analysis_window == ANALYSIS_WINDOW["sliding-12"]:
            start   = last_hour - timedelta(hours=6)
            end     = start     + timedelta(hours=12)
            self.logger.debug(f"Filter dataset to surrounding 12hrs {start} - {end} -> refresh each hour")

        elif self.analysis_window == ANALYSIS_WINDOW["forward-24"]:
            start   = last_hour
            end     = start     + timedelta(hours=24)
            self.logger.debug(f"Filter dataset to upcomming 24hrs {start} - {end} -> refresh each hour")
        
        elif self.analysis_window == ANALYSIS_WINDOW["forward-12"]:
            start   = last_hour
            end     = start     + timedelta(hours=12)
            self.logger.debug(f"Filter dataset to upcomming 12hrs {start} - {end} -> refresh each hour")
        
        else:  # self.analysis_window == ANALYSIS_WINDOW["publish"]:
            self.logger.debug(f"Do not filter the dataset, use the 48hrs dataset as retrieved")
            return self.get_48hrs_data()

        return {hour: price for hour, price in data.items() if start < hour < end }

    # ANALYSIS: Get max price in analysis window
    def get_max_price(self):
        return max(self.filtered_hourprices.values())

    # ANALYSIS: Get min price in analysis window
    def get_min_price(self):
        return min(self.filtered_hourprices.values())

    # ANALYSIS: Get timestamp of max price in analysis window
    def get_max_time(self):
        return max(self.filtered_hourprices, key=self.filtered_hourprices.get)

    # ANALYSIS: Get timestamp of min price in analysis window
    def get_min_time(self):
        return min(self.filtered_hourprices, key=self.filtered_hourprices.get)

    # ANALYSIS: Get avg price in analysis window
    # TODO import mean() from statistics
    def get_avg_price(self):
        prices = self.filtered_hourprices.values()
        return round(sum(prices) / len(prices), 5)        

    # ANALYSIS: Get percentage of current price relative to maximum in analysis window
    def get_percentage_of_max(self):
        return round(self.get_current_hourprice() / self.get_max_price() * 100, 1)

    # ANALYSIS: Get percentage of current price relative to spread (max-min) of analysis window
    def get_percentage_of_range(self):
        min = self.get_min_price()
        spread = self.get_max_price() - min
        current = self.get_current_hourprice() - min
        return round(current / spread * 100, 1)
    
    # --------------------------------------------------------------------------------------------------------------------------------
    # SERVICES: returns data from the coordinator cache, or directly from ENTSO when not availble
    # TODO: danger here for processing requests with huge periods -> suggest to limit to the 72 hrs of cached data
    async def get_energy_prices(self, start_date, end_date):
        # check if we have the data already
        if (
            len(self.get_data(start_date)) > MIN_HOURS
            and len(self.get_data(end_date)) > MIN_HOURS
        ):
            self.logger.debug(f"return prices from coordinator cache.")
            return {
                k: v
                for k, v in self.data.items()
                if k.date() >= start_date.date() and k.date() <= end_date.date()
            }
        return self.parse_hourprices(await self.fetch_prices(start_date, end_date))
