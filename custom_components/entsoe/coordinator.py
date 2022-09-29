from __future__ import annotations

import asyncio
from datetime import timedelta
import pandas as pd
from entsoe import EntsoePandasClient
import logging
from typing import List
from pytz import HOUR

from zeroconf import millis_to_seconds


from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt


class EntsoeCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(self, hass: HomeAssistant, api_key) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.api_key = api_key

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
            hour=0, minute=0, second=0, microsecond=0
        )

        tomorrow = today + pd.Timedelta(days=1)

        data_today = await self.fetchprices(today, tomorrow)

        return {
            "marketPricesElectricity": data_today,
        }

    async def fetchprices(self, start_date, end_date):
        try:
            resp = await self.hass.async_add_executor_job(
                self.api_update, start_date, end_date
            )

            data = resp.to_dict()
            return data

        except (asyncio.TimeoutError, KeyError) as error:
            raise UpdateFailed(f"Fetching energy price data failed: {error}") from error

    def api_update(self, start_date, end_date):
        client = EntsoePandasClient(api_key=self.api_key)

        return client.query_day_ahead_prices("NL", start=start_date, end=end_date)

    def processed_data(self):
        return {
            "elec": self.get_current_hourprices(self.data["marketPricesElectricity"]),
            "today_elec": self.get_hourprices(self.data["marketPricesElectricity"]),
        }

    def get_current_hourprices(self, hourprices) -> int:
        for hour, price in hourprices.items():
            if hour <= dt.utcnow() < hour + timedelta(hours=1):
                return price

    def get_hourprices(self, hourprices) -> List:
        return list(hourprices.values())
