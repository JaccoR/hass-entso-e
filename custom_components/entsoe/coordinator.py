from __future__ import annotations

import logging
import threading
from datetime import timedelta, datetime
from typing import Any, Dict, Optional

import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
from jinja2 import pass_context
from requests.exceptions import HTTPError

from .api_client import EntsoeClient
from .const import AREA_INFO, CALCULATION_MODE, DEFAULT_MODIFYER, ENERGY_SCALES
from .utils import get_interval_minutes, bucket_time

_LOGGER = logging.getLogger(__name__)

# This class contains two main tasks:
# 1. ENTSO: Refresh data from ENTSO.
# 2. ANALYSIS: Implement analysis (min/max/avg) on that data immediately after refresh.
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
        self.today: Optional[datetime] = None
        self.lock = threading.Lock()
        
        # Calculate the minimum required number of data points for 20 hours
        self.min_periods_required = 20 * (60 // self.period_minutes)

        # Storage for pre-calculated analysis data (Set to None initially)
        self._max_price: Optional[float] = None
        self._min_price: Optional[float] = None
        self._avg_price: Optional[float] = None
        self._max_time: Optional[datetime] = None
        self._min_time: Optional[datetime] = None

        # Check incase the sensor was setup using config flow.
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
    def parse_hourprices(self, hourprices: Dict[datetime, float]) -> Dict[datetime, float]:
        for hour, price in hourprices.items():
            hourprices[hour] = self.calc_price(value=price, fake_dt=hour)
        return hourprices

    # ENTSO: Triggered by HA to refresh the data
    async def _async_update_data(self) -> dict:
        """Get the latest data from ENTSO-e"""
        _LOGGER.debug("ENTSO-e DataUpdateCoordinator data update triggered.")

        now = dt.now()
        
        # Always update self.today at the start of the refresh
        self.today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 1. Clean up stale data at the start of the refresh (Day Rollover/Cleanup)
        if self.data is not None:
             self.data = {
                 hour: price
                 for hour, price in self.data.items()
                 if hour >= self.today - timedelta(days=1)
             }
        
        # 2. Check if a new API fetch is needed
        if self.check_update_needed(now) is False:
            _LOGGER.debug("Skipping api fetch. All data is already available.")
        else:
            yesterday = self.today - timedelta(days=1)
            tomorrow_evening = self.today + timedelta(days=2) 

            _LOGGER.debug(
                f"Fetching prices for start date: {yesterday} to end date: {tomorrow_evening}"
            )
            data = await self.fetch_prices(yesterday, tomorrow_evening)

            if data is not None:
                parsed_data = self.parse_hourprices(data)
                _LOGGER.debug(
                    f"Received pricing data from entso-e for {len(data)} periods"
                )
                self.data = parsed_data
            
        # 3. CRITICAL FIX: Run the analysis/calculation logic AFTER the data is refreshed
        with self.lock:
            self._run_analysis()
            
        return self.data


    def _run_analysis(self) -> None:
        """Calculates min/max/avg from the filtered price data and stores results."""
        
        prices_dict = self._filtered_prices
        
        if not prices_dict:
            _LOGGER.warning("Price analysis failed: Filtered price dictionary is empty.")
            # Reset stored values to None if data is missing
            self._max_price = self._min_price = self._avg_price = None
            self._max_time = self._min_time = None
            return

        prices = prices_dict.values()
        
        try:
            self._max_price = max(prices)
            self._min_price = min(prices)
            self._avg_price = round(sum(prices) / len(prices), 5)
            self._max_time = max(prices_dict, key=prices_dict.get)
            self._min_time = min(prices_dict, key=prices_dict.get)

        except Exception as exc:
            _LOGGER.error(f"Error during price analysis calculation: {exc}")
            # Ensure values are reset if calculation fails
            self._max_price = self._min_price = self._avg_price = None
            self._max_time = self._min_time = None

    # ENTSO: check if we need to refresh the data.
    def check_update_needed(self, now):
        if self.data is None:
            return True
        # Check if today's data is short
        if len(self.get_data_today()) < self.min_periods_required:
            return True
        # Check if tomorrow's data is short AND it's late enough (after 11 AM)
        if len(self.get_data_tomorrow()) < self.min_periods_required and now.hour > 11:
            return True
        return False

    # ENTSO: new prices using an async job
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
            # Raised exception will prevent the entity from becoming available (correct behavior)
            raise UpdateFailed(f"ENTSO-e API fetch failed: {exc}") from exc

    # ENTSO: the async fetch job itself
    def api_update(self, start_date, end_date, api_key):
        client = EntsoeClient(api_key=api_key, period=self.period)
        return client.query_day_ahead_prices(
            country_code=self.area, start=start_date, end=end_date
        )

    # ENTSO: Return the data for the given date
    def get_data(self, date):
        # Must ensure self.data is not None before accessing
        if self.data is None:
             return {}
        return {k: v for k, v in self.data.items() if k.date() == date.date()}

    # ENTSO: Return the data for today
    def get_data_today(self):
        return self.get_data(self.today) if self.today else {}

    # ENTSO: Return the data for tomorrow
    def get_data_tomorrow(self):
        return self.get_data(self.today + timedelta(days=1)) if self.today else {}

    # SENSOR: Do we have data available for today
    def today_data_available(self):
        # Use the dynamic minimum periods required
        return len(self.get_data_today()) >= self.min_periods_required

    @property
    def current_bucket_time(self):
        return bucket_time(dt.now(), self.period_minutes)

    # SENSOR: Getters now read pre-calculated values
    def get_current_price(self) -> Optional[float]:
        return self.data.get(self.current_bucket_time) if self.data else None

    def get_next_price(self) -> Optional[float]:
        return self.data.get(
            self.current_bucket_time + timedelta(minutes=self.period_minutes)
        ) if self.data else None

    def get_prices_today(self):
        return self.get_timestamped_prices(self.get_data_today())

    def get_prices_tomorrow(self):
        return self.get_timestamped_prices(self.get_data_tomorrow())

    def get_prices(self):
        if self.data is None:
             return []
        
        periods_48hrs = 48 * (60 // self.period_minutes)
        
        if len(self.data) > periods_48hrs:
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

    # ANALYSIS: filter the prices on which to apply the calculations based on the calculation_mode
    @property
    def _filtered_prices(self) -> Dict[datetime, float]:
        """Filter the prices based on the calculation mode."""
        if self.data is None:
             return {}
        
        periods_48hrs = 48 * (60 // self.period_minutes)
        
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
            self.calculation_mode == CALCULATION_MODE["publish"] and len(self.data) > periods_48hrs
        ):
            return {ts: price for ts, price in self.data.items() if ts >= self.today}
        # publish <=48 hrs of data = calculations made on all data of yesterday and today (48 hrs)
        elif self.calculation_mode == CALCULATION_MODE["publish"]:
            return {
                ts: price
                for ts, price in self.data.items()
                if ts >= self.today - timedelta(days=1)
            }

        _LOGGER.error("Unknown calculation mode, returning empty filtered prices")
        return {}
    
    # SENSOR: Getters now read from pre-calculated properties
    def get_max_price(self) -> Optional[float]:
        return self._max_price

    def get_min_price(self) -> Optional[float]:
        return self._min_price

    def get_max_time(self) -> Optional[datetime]:
        return self._max_time

    def get_min_time(self) -> Optional[datetime]:
        return self._min_time

    def get_avg_price(self) -> Optional[float]:
        return self._avg_price

    # SENSOR: Get percentage of current price relative to maximum of filtered period
    def get_percentage_of_max(self) -> Optional[float]:
        current = self.get_current_price()
        max_price = self.get_max_price()
        if current is None or max_price is None or max_price == 0:
            return None
        return round(current / max_price * 100, 1)

    # SENSOR: Get percentage of current price relative to spread (max-min) of filtered period
    def get_percentage_of_range(self) -> Optional[float]:
        min_price = self.get_min_price()
        max_price = self.get_max_price()
        current = self.get_current_price()
        
        if min_price is None or max_price is None or current is None:
            return None

        spread = max_price - min_price
        if spread == 0:
            return 0.0 # Price is flat
            
        current_relative = current - min_price
        return round(current_relative / spread * 100, 1)
        
    # SERVICES: returns data from the coordinator cache, or directly from ENTSO when not availble
    async def get_energy_prices(self, start_date, end_date):
        # check if we have the data already
        if (
            len(self.get_data(start_date)) >= self.min_periods_required
            and len(self.get_data(end_date)) >= self.min_periods_required
        ):
            _LOGGER.debug("return prices from coordinator cache.")
            return {
                k: v
                for k, v in self.data.items()
                if k.date() >= start_date.date() and k.date() <= end_date.date()
            }
        
        # If not enough data, fetch it and parse it on the fly
        data = await self.fetch_prices(start_date, end_date)
        return self.parse_hourprices(data)