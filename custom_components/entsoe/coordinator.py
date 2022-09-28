from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import pandas as pd
from entsoe import EntsoePandasClient
import logging
from typing import List, Tuple

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt
from .const import API_KEY


class EntsoeCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(self, hass: HomeAssistant, websession) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.websession = websession

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

        # We request data for today up until the day after tomorrow.
        # This is to ensure we always request all available data.
        today = pd.Timestamp(dt.start_of_local_day())
        tomorrow = today + pd.Timedelta(days=1)

        # Fetch data for today and tomorrow separately,
        # because the gas prices response only contains data for the first day of the query
        data_today = await self.fetchprices(today, tomorrow)

        return {
            "marketPricesElectricity": data_today,
        }

    def update(self, start_date, end_date):
        client = EntsoePandasClient(api_key=API_KEY)
        return client.query_day_ahead_prices("NL", start=start_date, end=end_date)

    async def fetchprices(self, start_date, end_date):
        try:
            resp = await self.hass.async_add_executor_job(
                self.update, start_date, end_date
            )

            data = resp.to_dict()
            self.logger.debug("werkt dit?????")
            self.logger.debug(data)
            return data

        except (asyncio.TimeoutError, aiohttp.ClientError, KeyError) as error:
            raise UpdateFailed(f"Fetching energy price data failed: {error}") from error

    def processed_data(self):
        self.logger.debug("hierzo entsoe")

        return {
            'elec': self.get_current_hourprices(self.data['marketPricesElectricity']),
            'today_elec': self.get_hourprices(self.data['marketPricesElectricity'])
        }

    def get_current_hourprices(self, hourprices) -> int:
        for hour, price in hourprices.items():
            if hour <= dt.utcnow() < hour + timedelta(hours=1):
                self.logger.debug("entsoe current prices")
                self.logger.debug(price)
                return price

    def get_hourprices(self, hourprices) -> List:
        self.logger.debug("werkt dit??")
        self.logger.debug(list(hourprices.values()))
        return list(hourprices.values())
