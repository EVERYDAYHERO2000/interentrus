"""Micronmedia API protocol tests against synthetic responses."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import aiohttp
import pytest
from isp_providers import AuthenticationError, ProviderError
from isp_providers.micron import MicronClient, forecast_date, money, parse_account

BALANCE = {
    "success": True,
    "balance": 1250.25,
    "balanceState": True,
    "estimateDate": "2026-11-01T00:00:00+03:00",
    "amountForUnlock": 0,
}
TARIFF = {
    "success": True,
    "tariffArray": [{"tariffUserName": "Test 100", "tariffCost": 900, "tariffTimeUnit": "MONTHLY"}],
}
HISTORY = {"success": True, "eventArray": [{"amount": 1000}, {"amount": -900}, {"amount": -300}]}


def test_fields_and_optional_history():
    data = parse_account(BALANCE, TARIFF, HISTORY, date(2026, 10, 20))
    assert data.amount == Decimal("1250.25")
    assert data.sufficient_until == date(2026, 11, 1)
    assert data.minimum_payment == 0
    assert data.monthly_fee == 900
    assert data.tariff == "Test 100"
    assert data.month_expenses == 1200


@pytest.mark.parametrize("value", [None, True, "NaN", "Infinity", {}, "error"])
def test_invalid_money(value):
    assert money(value) is None


@pytest.mark.parametrize("value", [None, "", "not-a-date", "2026-02-31"])
def test_invalid_forecast(value):
    assert forecast_date(value) is None


def test_forecast_is_not_shown_for_inactive_balance():
    assert parse_account(BALANCE | {"balanceState": False}).sufficient_until is None


def test_missing_optional_fields():
    data = parse_account({"success": True, "balance": 0})
    assert data.amount == 0
    assert data.minimum_payment is None
    assert data.sufficient_until is None
    assert data.monthly_fee is None
    assert data.month_expenses is None


def test_nonmonthly_tariff_is_not_treated_as_monthly():
    data = parse_account(
        BALANCE,
        {"success": True, "tariffArray": [TARIFF["tariffArray"][0] | {"tariffTimeUnit": "DAILY"}]},
    )
    assert data.monthly_fee is None
    assert data.tariff == "Test 100"


def test_corrupt_history_does_not_return_partial_expenses():
    assert (
        parse_account(
            BALANCE, history={"success": True, "eventArray": [{"amount": -50}, {"amount": None}]}
        ).month_expenses
        is None
    )


def test_empty_history_has_zero_expenses():
    assert parse_account(BALANCE, history={"success": True, "eventArray": []}).month_expenses == 0


@pytest.mark.parametrize(
    "balance",
    [{"success": False, "balance": 100}, {"success": True}, {"success": True, "balance": True}],
)
def test_missing_balance_fails_closed(balance):
    with pytest.raises(ProviderError):
        parse_account(balance)


@pytest.mark.asyncio
async def test_session_renewal():
    client = MicronClient(None, "test", "secret")
    client._request = AsyncMock(
        side_effect=[AuthenticationError(), {"success": True}, BALANCE, TARIFF, HISTORY]
    )
    data = await client.async_balance(today=date(2026, 10, 20))
    assert data.amount == Decimal("1250.25")
    assert client._request.call_args_list[1].kwargs["json"] == {
        "login": "test",
        "password": "secret",
        "rememberMe": True,
    }
    assert client._request.call_args_list[-1].kwargs["params"]["startDate"] == "2026-10-01 00:00:00"


@pytest.mark.asyncio
async def test_bad_credentials():
    client = MicronClient(None, "test", "wrong")
    client._request = AsyncMock(
        side_effect=[AuthenticationError(), {"success": False, "error": "Rejected"}]
    )
    with pytest.raises(AuthenticationError):
        await client.async_balance()


@pytest.mark.asyncio
async def test_optional_endpoint_failure_keeps_balance():
    client = MicronClient(None, "test", "secret")
    client._request = AsyncMock(side_effect=[BALANCE, aiohttp.ClientError(), ProviderError()])
    data = await client.async_balance()
    assert data.amount == Decimal("1250.25")
    assert data.monthly_fee is None
    assert data.month_expenses is None


@pytest.mark.asyncio
async def test_no_foreign_endpoint():
    client = MicronClient(None, "test", "secret")
    with pytest.raises(ProviderError):
        await client._request("POST", "https://example.org/login", json={"password": "secret"})


class FakeResponse:
    def __init__(self, data, status=200, headers=None):
        import json

        self.body = json.dumps(data)
        self.status = status
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientError("HTTP error")

    async def text(self):
        return self.body


@pytest.mark.asyncio
async def test_login_routing_header_and_identity():
    from unittest.mock import Mock

    session = Mock()
    session.request.return_value = FakeResponse(
        {"success": True}, headers={"lino_segment": "segment-a"}
    )
    client = MicronClient(session, "test", "secret")
    await client.async_login()
    assert client.headers["lino_segment"] == "segment-a"
    assert session.request.call_args.kwargs["allow_redirects"] is False
    assert session.request.call_args.args[1] == "https://app.micmedia.ru/api/mobile/login"
    assert (
        client.headers["x-mobile-uid"]
        != MicronClient(None, "other", "other").headers["x-mobile-uid"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [202, 302, 307])
async def test_redirects_never_followed(status):
    from unittest.mock import Mock

    session = Mock()
    session.request.return_value = FakeResponse(
        {}, status=status, headers={"Location": "https://example.org"}
    )
    with pytest.raises(ProviderError):
        await MicronClient(session, "test", "secret").async_login()
    assert session.request.call_count == 1
