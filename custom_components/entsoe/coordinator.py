from __future__ import annotations

import asyncio
from datetime import timedelta
import pandas as pd
from entsoe import EntsoePandasClient
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

class EntsoeCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(self, hass: HomeAssistant, api_key, country) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.api_key = api_key
        self.country = country

        logger = logging.getLogger(__name__)
        super().__init__(
            hass,
            logger,
            name="ENTSO-e coordinator",
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_data(self) -> dict:
        """Get the latest data from ENTSO-e"""
        self.logger.debug("Fetching ENTSO-e data")

        time_zone = dt.now().tzinfo
        # We request data for today up until tomorrow.
        today = pd.Timestamp.now(tz=str(time_zone)).replace(
            hour=0, minute=0, second=0
        )

        tomorrow = today + pd.Timedelta(days=1)

        data_today = await self.fetch_prices(today, tomorrow)

        return {
            "marketPricesElectricity": data_today,
        }

    async def fetch_prices(self, start_date, end_date):
        try:
            resp = await self.hass.async_add_executor_job(
                self.api_update, start_date, end_date, self.api_key
            )

            data = resp.to_dict()
            return data

        except (asyncio.TimeoutError, KeyError) as error:
            raise UpdateFailed(f"Fetching energy price data failed: {error}") from error

    def api_update(self, start_date, end_date, api_key):
        client = EntsoePandasClient(api_key=api_key)

        return client.query_day_ahead_prices(self.country, start=start_date, end=end_date)

    def processed_data(self):
        return {
            "elec": self.get_current_hourprice(self.data["marketPricesElectricity"]),
            "elec_next_hour": self.get_next_hourprice(self.data["marketPricesElectricity"]),
            "today_elec": self.get_hourprices(self.data["marketPricesElectricity"]),
            "time_min_price": self.get_min_time(self.data["marketPricesElectricity"]),
            "time_max_price": self.get_max_time(self.data["marketPricesElectricity"])
        }
    def get_next_hourprice(self, hourprices) -> int:
        for hour, price in hourprices.items():
            if hour - timedelta(hours=1) <= dt.utcnow() < hour:
                return price

    def get_current_hourprice(self, hourprices) -> int:
        for hour, price in hourprices.items():
            if hour <= dt.utcnow() < hour + timedelta(hours=1):
                return price

    def get_hourprices(self, hourprices) -> list:
        return list(hourprices.values())

    def get_max_time(self, hourprices):
        return max(hourprices, key=hourprices.get)

    def get_min_time(self, hourprices):
        return min(hourprices, key=hourprices.get)

