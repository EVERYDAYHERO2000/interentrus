"""ISP account balances."""

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN
from .coordinator import BalanceCoordinator
from .migration import obsolete_entity_ids
from .providers.factory import create_client

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass, entry):
    session = async_create_clientsession(hass)
    coordinator = BalanceCoordinator(
        hass,
        entry,
        create_client(
            entry.data["provider"], session, entry.data["username"], entry.data["password"]
        ),
    )
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        registry = er.async_get(hass)
        for entity_id in obsolete_entity_ids(
            er.async_entries_for_config_entry(registry, entry.entry_id), entry.unique_id, DOMAIN
        ):
            registry.async_remove(entity_id)
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
