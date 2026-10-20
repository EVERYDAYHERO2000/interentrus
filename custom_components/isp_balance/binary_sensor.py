"""Top-up reminder."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.util import dt as dt_util

from .const import CONF_WARNING_DAYS, DEFAULT_WARNING_DAYS
from .entity import DailyEntity
from .logic import needs_top_up


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TopUpSensor(entry.runtime_data, entry)])


class TopUpSensor(DailyEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:wallet-plus"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_needs_top_up"
        self._attr_name = f"{entry.title} Пора пополнить"
        self.threshold = entry.options.get(CONF_WARNING_DAYS, DEFAULT_WARNING_DAYS)

    @property
    def is_on(self):
        return needs_top_up(self.coordinator.data, dt_util.now().date(), self.threshold)

    @property
    def extra_state_attributes(self):
        return {"warning_days": self.threshold}
