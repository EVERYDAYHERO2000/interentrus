"""Provider account sensors."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.util import dt as dt_util

from .entity import DailyEntity
from .logic import daily_cost, remaining_days

SENSORS = [
    ("balance", "Баланс", "amount", SensorDeviceClass.MONETARY, "RUB", "mdi:wallet"),
    (
        "sufficient_until",
        "Хватит до",
        "sufficient_until",
        SensorDeviceClass.DATE,
        None,
        "mdi:calendar-clock",
    ),
    (
        "minimum_payment",
        "Минимальный платёж",
        "minimum_payment",
        SensorDeviceClass.MONETARY,
        "RUB",
        "mdi:cash",
    ),
    (
        "monthly_fee",
        "Абонентская плата",
        "monthly_fee",
        SensorDeviceClass.MONETARY,
        "RUB",
        "mdi:cash-sync",
    ),
    (
        "month_expenses",
        "Расходы за текущий месяц",
        "month_expenses",
        SensorDeviceClass.MONETARY,
        "RUB",
        "mdi:cash-minus",
    ),
    ("tariff", "Текущий тариф", "tariff", None, None, "mdi:network"),
    (
        "daily_cost",
        "Стоимость дня",
        None,
        SensorDeviceClass.MONETARY,
        "RUB",
        "mdi:cash-clock",
    ),
    (
        "remaining_days",
        "Осталось дней",
        None,
        SensorDeviceClass.DURATION,
        UnitOfTime.DAYS,
        "mdi:calendar-end",
    ),
]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(AccountSensor(entry.runtime_data, entry, spec) for spec in SENSORS)


class AccountSensor(DailyEntity, SensorEntity):
    def __init__(self, coordinator, entry, spec):
        super().__init__(coordinator)
        key, name, self.field, device_class, unit, icon = spec
        self.key = key
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_name = f"{entry.title} {name}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def native_value(self):
        data = self.coordinator.data
        today = dt_util.now().date()
        if self.key == "daily_cost":
            return daily_cost(data, today)
        if self.key == "remaining_days":
            return remaining_days(data, today)
        if self.key == "month_expenses" and data.billing_date is not None:
            if (today.year, today.month) != (
                data.billing_date.year,
                data.billing_date.month,
            ):
                return None
        return getattr(data, self.field)
