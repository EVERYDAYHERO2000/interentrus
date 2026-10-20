"""Local billing calculations, calendar boundaries and threshold precision."""

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "isp_logic", Path(__file__).resolve().parents[1] / "custom_components/isp_balance/logic.py"
)
logic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logic)


def data(balance="100", fee="1069"):
    return SimpleNamespace(
        amount=Decimal(balance), monthly_fee=Decimal(fee) if fee is not None else None
    )


@pytest.mark.parametrize(
    "today,expected",
    [
        (date(2026, 10, 20), "34.48"),
        (date(2026, 2, 20), "38.18"),
        (date(2028, 2, 20), "36.86"),
        (date(2026, 11, 1), "35.63"),
    ],
)
def test_calendar_daily_cost(today, expected):
    assert logic.daily_cost(data(), today) == Decimal(expected)


@pytest.mark.parametrize(
    "balance,threshold,expected",
    [
        ("30.01", 3, False),
        ("30", 3, True),
        ("29.99", 3, True),
        ("0", 0, True),
        ("0.01", 0, False),
        ("-1", 0, True),
    ],
)
def test_threshold_from_balance_and_fee(balance, threshold, expected):
    assert logic.needs_top_up(data(balance, "310"), date(2026, 10, 20), threshold) is expected


def test_top_up_uses_unrounded_rate():
    assert logic.needs_top_up(data("96.78", "1000"), date(2026, 10, 20), 3) is False
    assert logic.needs_top_up(data("96.77", "1000"), date(2026, 10, 20), 3) is True


@pytest.mark.parametrize("fee", [None, "-10"])
def test_unknown_or_invalid_fee(fee):
    assert logic.daily_cost(data(fee=fee), date(2026, 10, 20)) is None
    assert logic.needs_top_up(data(fee=fee), date(2026, 10, 20), 3) is None


@pytest.mark.parametrize("balance", ["0", "100"])
def test_free_tariff_does_not_need_top_up(balance):
    assert logic.needs_top_up(data(balance, "0"), date(2026, 10, 20), 3) is False


def test_debt_requires_top_up_even_without_fee():
    assert logic.needs_top_up(data("-1", None), date(2026, 10, 20), 3) is True
