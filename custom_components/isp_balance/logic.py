"""Local calculations based only on provider balance and monthly fee."""

from calendar import monthrange
from decimal import ROUND_HALF_UP, Decimal


def daily_cost(data, today):
    if data.monthly_fee is None or data.monthly_fee < 0:
        return None
    return (data.monthly_fee / monthrange(today.year, today.month)[1]).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def needs_top_up(data, today, threshold):
    if data.amount < 0:
        return True
    if data.monthly_fee is None or data.monthly_fee < 0:
        return None
    if data.monthly_fee == 0:
        return False
    # Compare without rounding the daily rate: a kopeck must not shift the threshold.
    return (
        data.amount
        <= data.monthly_fee * Decimal(threshold) / monthrange(today.year, today.month)[1]
    )
