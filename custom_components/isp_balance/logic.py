"""Calculations shared by sensors; dates are supplied in HA local time."""

from calendar import monthrange
from decimal import ROUND_HALF_UP, Decimal


def remaining_days(data, today):
    if data.sufficient_until is None:
        return None
    return max(0, (data.sufficient_until - today).days)


def daily_cost(data, today):
    if data.monthly_fee is None or data.billing_date is None:
        return None
    # Do not extrapolate an old tariff into a new month after a failed refresh.
    if (today.year, today.month) != (data.billing_date.year, data.billing_date.month):
        return None
    return (data.monthly_fee / monthrange(today.year, today.month)[1]).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def needs_top_up(data, today, threshold):
    if data.amount <= 0 or (data.minimum_payment is not None and data.minimum_payment > 0):
        return True
    days = remaining_days(data, today)
    return None if days is None else days <= threshold
