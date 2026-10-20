"""ISP account balances."""

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .coordinator import BalanceCoordinator
from .providers.netnord import NetnordClient

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass, entry):
    session = async_create_clientsession(hass)
    coordinator = BalanceCoordinator(
        hass,
        entry,
        NetnordClient(session, entry.data["username"], entry.data["password"]),
    )
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        session.detach()
        raise
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.client.session.detach()
    return unloaded


async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
