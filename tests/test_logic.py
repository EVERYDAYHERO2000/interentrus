"""Calendar calculations, threshold boundaries and missing forecasts."""

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "isp_logic",
    Path(__file__).resolve().parents[1] / "custom_components/isp_balance/logic.py",
)
logic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logic)


def data(**kwargs):
    fields = dict(
        amount=Decimal(100),
        minimum_payment=Decimal(0),
        sufficient_until=date(2026, 10, 31),
        monthly_fee=Decimal(1069),
        billing_date=date(2026, 10, 20),
    )
    return SimpleNamespace(**(fields | kwargs))


@pytest.mark.parametrize(
    "today,days",
    [(date(2026, 10, 20), 11), (date(2026, 10, 31), 0), (date(2026, 11, 1), 0)],
)
def test_remaining_days(today, days):
    assert logic.remaining_days(data(), today) == days


@pytest.mark.parametrize(
    "today,expected",
    [
        (date(2026, 10, 20), "34.48"),
        (date(2026, 2, 20), "38.18"),
        (date(2028, 2, 20), "36.86"),
    ],
)
def test_month_lengths(today, expected):
    assert logic.daily_cost(data(billing_date=today), today) == Decimal(expected)


def test_old_month_rate_unknown():
    assert logic.daily_cost(data(), date(2026, 11, 1)) is None


@pytest.mark.parametrize(
    "today,expected",
    [
        (date(2026, 10, 27), False),
        (date(2026, 10, 28), True),
        (date(2026, 11, 1), True),
    ],
)
def test_threshold_boundary(today, expected):
    assert logic.needs_top_up(data(), today, 3) is expected


@pytest.mark.parametrize(
    "fields",
    [
        dict(amount=Decimal(0)),
        dict(amount=Decimal(-1)),
        dict(minimum_payment=Decimal(10)),
    ],
)
def test_payment_required_without_forecast(fields):
    assert logic.needs_top_up(data(sufficient_until=None, **fields), date(2026, 10, 20), 3) is True


def test_missing_forecast_unknown():
    assert logic.remaining_days(data(sufficient_until=None), date(2026, 10, 20)) is None
    assert logic.needs_top_up(data(sufficient_until=None), date(2026, 10, 20), 3) is None
