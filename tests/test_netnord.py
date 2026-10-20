"""Client tests without requiring a Home Assistant installation."""

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
        sidebar() + sidebar("999,01"),
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


@pytest.mark.parametrize("forecast", ["", "Хватит до 31.02.2026", "Хватит до неизвестно"])
def test_missing_or_invalid_forecast_keeps_balance(forecast):
    html = sidebar().replace("Хватит до 31.12.2026", forecast)
    assert parse_balance(html).amount == Decimal("123.45")


ACCOUNT = """<div class="carbon_modules_abonentstatus"><table>
<tr><td>Статус</td><td>Новый</td></tr>
<tr><td>Тариф</td><td>"Тестовый": 1000.0 руб. / мес.</td></tr>
</table></div><div class="carbon_modules_currentmonthexpenses"><table>
<tr><td>Интернет</td><td>500,25</td></tr>
<tr><td>Услуга</td><td>20,00</td></tr></table></div>"""


def test_monthly_fee_from_account():
    data = parse_balance(sidebar() + ACCOUNT)
    assert data.monthly_fee == Decimal(1000)
    assert data.amount == Decimal("123.45")


def test_monthly_fee_unknown_when_absent():
    assert parse_balance(sidebar()).monthly_fee is None


def test_unused_expenses_do_not_affect_balance_and_fee():
    data = parse_balance(sidebar() + ACCOUNT.replace("20,00", "ошибка"))
    assert data.monthly_fee == Decimal(1000)
    assert data.amount == Decimal("123.45")


def test_unknown_tariff_format_does_not_guess_fee():
    data = parse_balance(
        sidebar() + ACCOUNT.replace('"Тестовый": 1000.0 руб. / мес.', "Особый тариф")
    )
    assert data.monthly_fee is None


@pytest.mark.asyncio
async def test_login_followed_by_authenticated_account_page():
    client = NetnordClient(None, "test", "secret")
    client._request = AsyncMock(side_effect=[LOGIN, LOGIN, sidebar(), sidebar() + ACCOUNT])
    assert (await client.async_balance()).monthly_fee == Decimal(1000)
    assert client._request.call_args_list[-1].args == ("GET", ACCOUNT_URL)


@pytest.mark.parametrize("amount", ["123,45", "0,00", "-25,10"])
def test_unrepaired_nested_provider_paragraphs(amount):
    html = f"""<div class="carbon_modules_userinfosidebar">
    <div class="sidebar-block-header">Баланс ЛС:</div>
    <div class="user-data"><p class="no-margin">
    <p class="no-margin">{amount} <i class="fa fa-rub"></i></p>
    <p><small>Хватит до 31.10.2026</small></p></p></div>
    <div class="sidebar-block-header">Мин. платеж:</div>
    <div class="user-data"><p class="no-margin"><p class="no-margin">0,00 <i class="fa fa-rub"></i></p></p></div>
    </div>"""
    result = parse_balance(html)
    assert result.amount == Decimal(amount.replace(",", "."))


@pytest.mark.parametrize("currency", ["₽", "руб.", "RUB"])
def test_explicit_currency_text(currency):
    assert parse_balance(sidebar("123,45 " + currency)).amount == Decimal("123.45")


def test_two_amounts_in_one_balance_block_fail_closed():
    with pytest.raises(ProviderError):
        parse_balance(sidebar().replace("<p></p>", "<p>456,00</p>", 1))


def test_desktop_and_mobile_copies_of_balance_are_identical():
    # The live cabinet renders both menus in the same HTML response.
    html = (
        '<nav class="desktop-menu">'
        + sidebar()
        + '</nav><nav class="mobile-menu">'
        + sidebar()
        + "</nav>"
    )
    result = parse_balance(html)
    assert result.amount == Decimal("123.45")


def test_unused_desktop_mobile_forecasts_do_not_affect_balance():
    html = sidebar() + sidebar().replace("31.12.2026", "30.12.2026")
    assert parse_balance(html).amount == Decimal("123.45")


def test_unused_minimum_payments_do_not_affect_balance():
    html = sidebar() + sidebar().replace("999,00", "111,00")
    assert parse_balance(html).amount == Decimal("123.45")


def test_hidden_personal_information_sidebar_is_not_a_balance():
    html = (
        sidebar()
        + sidebar()
        + '<div class="carbon_modules_userinfosidebar"><div class="sidebar-block-header">Номер лицевого счета</div><div class="user-data"><p>123456789</p></div></div>'
    )
    assert parse_balance(html).amount == Decimal("123.45")
