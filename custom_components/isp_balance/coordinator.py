"""Periodic account refresh."""

import logging
from datetime import timedelta

import aiohttp
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .providers import AuthenticationError, ProviderError


class BalanceCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="ISP Balance",
            config_entry=entry,
            update_interval=timedelta(hours=1),
        )
        self.client = client

    async def _async_update_data(self):
        try:
            return await self.client.async_balance(today=dt_util.now().date())
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (aiohttp.ClientError, TimeoutError, ProviderError) as err:
            raise UpdateFailed("Could not retrieve provider balance") from err
