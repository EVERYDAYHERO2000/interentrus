"""Shared entity lifecycle for daily calculations."""

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class DailyEntity(CoordinatorEntity):
    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(self.hass, self._midnight, hour=0, minute=0, second=0)
        )

    @callback
    def _midnight(self, now):
        self.async_write_ha_state()
