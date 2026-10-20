"""Client tests without requiring a Home Assistant installation."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from isp_providers import AuthenticationError, ProviderError
from isp_providers.netnord import ACCOUNT_URL, NetnordClient, parse_balance


# Minimal structural fixture; no account identifiers, cookies, or personal data.
def sidebar(amount="123,45"):
    return f"""<div class="carbon_modules_userinfosidebar"><div class="contract-info">
    <div class="sidebar-block-header">Баланс ЛС:</div>
    <div class="user-data"><p></p><p class="no-margin">{amount} <i class="fa fa-rub"></i></p><p><small>Хватит до 31.12.2026</small></p><p></p></div>
    <div class="sidebar-block-header">Мин. платеж:</div>
    <div class="user-data"><p></p><p>999,00</p></div></div></div>"""


LOGIN = """<form method="post" action="/cabinet/welcome/">
<input name="module_token" value="token"><input name="module_token_unique" value="unique">
<input name="LOGIN"><input name="PASSWD" type="password"></form>"""


@pytest.mark.parametrize(
    "amount,expected",
    [
        ("123,45", "123.45"),
        ("-25,10", "-25.10"),
        ("0,00", "0.00"),
        ("1\xa0234,56", "1234.56"),
        ("−2,50", "-2.50"),
    ],
)
def test_balance(amount, expected):
    assert parse_balance(sidebar(amount)).amount == Decimal(expected)


@pytest.mark.parametrize(
    "html",
    [
        "<p>Balance unavailable</p>",
        sidebar("ошибка"),
        sidebar() + sidebar(),
        sidebar("NaN"),
    ],
)
def test_fail_closed(html):
    with pytest.raises(ProviderError):
        parse_balance(html)


@pytest.mark.asyncio
async def test_expired_session_logs_in_with_fresh_tokens():
    client = NetnordClient(None, "test", "secret")
    client._request = AsyncMock(side_effect=[LOGIN, LOGIN, sidebar(), sidebar()])
    assert (await client.async_balance()).amount == Decimal("123.45")
    assert client._request.call_args_list[-2].kwargs["data"] == {
        "module_token": "token",
        "module_token_unique": "unique",
        "LOGIN": "test",
        "PASSWD": "secret",
    }


@pytest.mark.asyncio
async def test_existing_session_skips_login():
    client = NetnordClient(None, "test", "secret")
    client._request = AsyncMock(return_value=sidebar())
    await client.async_balance()
    client._request.assert_awaited_once_with("GET", ACCOUNT_URL)


@pytest.mark.asyncio
async def test_rejected_credentials():
    client = NetnordClient(None, "test", "wrong")
    client._request = AsyncMock(return_value=LOGIN)
    with pytest.raises(AuthenticationError):
        await client.async_balance()


@pytest.mark.asyncio
async def test_foreign_destination_never_requested():
    client = NetnordClient(None, "test", "secret")
    with pytest.raises(ProviderError):
        await client._request("POST", "https://example.org/", data={"PASSWD": "secret"})


def test_sufficient_until_date():
    assert parse_balance(sidebar()).sufficient_until == date(2026, 12, 31)


@pytest.mark.parametrize("forecast", ["", "Хватит до 31.02.2026", "Хватит до неизвестно"])
def test_missing_or_invalid_forecast_keeps_balance(forecast):
    html = sidebar().replace("Хватит до 31.12.2026", forecast)
    result = parse_balance(html)
    assert result.sufficient_until is None
    assert result.amount == Decimal("123.45")


ACCOUNT = """<div class="carbon_modules_abonentstatus"><table>
<tr><td>Статус</td><td>Новый</td></tr>
<tr><td>Тариф</td><td>"Тестовый": 1000.0 руб. / мес.</td></tr>
</table></div><div class="carbon_modules_currentmonthexpenses"><table>
<tr><td>Интернет</td><td>500,25</td></tr>
<tr><td>Услуга</td><td>20,00</td></tr></table></div>"""


def test_account_fields_and_expenses_sum():
    data = parse_balance(sidebar() + ACCOUNT, today=date(2026, 10, 20))
    assert data.minimum_payment == Decimal(999)
    assert data.tariff == "Тестовый"
    assert data.monthly_fee == Decimal(1000)
    assert data.month_expenses == Decimal("520.25")
    assert data.billing_date == date(2026, 10, 20)


def test_optional_fields_are_unknown_when_absent():
    data = parse_balance(sidebar())
    assert data.tariff is None
    assert data.monthly_fee is None
    assert data.month_expenses is None


def test_corrupt_expense_does_not_report_partial_total():
    data = parse_balance(sidebar() + ACCOUNT.replace("20,00", "ошибка"))
    assert data.month_expenses is None
    assert data.amount == Decimal("123.45")


def test_unknown_tariff_format_keeps_name_without_guessing_fee():
    data = parse_balance(
        sidebar() + ACCOUNT.replace('"Тестовый": 1000.0 руб. / мес.', "Особый тариф")
    )
    assert data.tariff == "Особый тариф"
    assert data.monthly_fee is None


@pytest.mark.asyncio
async def test_login_followed_by_authenticated_account_page():
    client = NetnordClient(None, "test", "secret")
    client._request = AsyncMock(side_effect=[LOGIN, LOGIN, sidebar(), sidebar() + ACCOUNT])
    assert (await client.async_balance()).monthly_fee == Decimal(1000)
    assert client._request.call_args_list[-1].args == ("GET", ACCOUNT_URL)
