"""Micronmedia's Linologi mobile API, as used by its public web client."""

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import aiohttp

from . import AccountBalance, AuthenticationError, ProviderError

BASE_URL = "https://app.micmedia.ru"
API_URL = f"{BASE_URL}/api/mobile"


class MicronClient:
    """Keep cookies, device identifier and routing segment in one account session."""

    def __init__(self, session, username, password):
        self.session = session
        self.username = username
        self.password = password
        self.headers = {"x-mobile-uid": str(uuid4())}

    async def _request(self, method, path, **kwargs):
        if path not in {"/login", "/balance", "/tariff", "/statistics"}:
            raise ProviderError("Unexpected API endpoint")
        async with self.session.request(
            method,
            f"{API_URL}{path}",
            headers=self.headers,
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=30),
            **kwargs,
        ) as response:
            if response.status in (401, 403):
                raise AuthenticationError("Provider session rejected")
            # Never follow a credential-bearing redirect or an interactive SSO flow.
            if response.status in (202, 301, 302, 303, 307, 308):
                raise ProviderError("Interactive or redirected login is unsupported")
            response.raise_for_status()
            try:
                data = json.loads(await response.text(), parse_float=Decimal)
            except (ValueError, UnicodeError) as err:
                raise ProviderError("Invalid API JSON") from err
            if not isinstance(data, dict):
                raise ProviderError("Invalid API response")
            if path == "/login" and (segment := response.headers.get("lino_segment")):
                self.headers["lino_segment"] = segment
            return data

    async def async_login(self):
        self.headers.pop("lino_segment", None)
        data = await self._request(
            "POST",
            "/login",
            json={
                "login": self.username,
                "password": self.password,
                "rememberMe": True,
            },
        )
        if data.get("success") is not True:
            raise AuthenticationError("Provider rejected credentials")

    async def _read(self, path, **kwargs):
        try:
            data = await self._request("GET", path, **kwargs)
        except AuthenticationError:
            await self.async_login()
            data = await self._request("GET", path, **kwargs)
        if data.get("success") is not True:
            raise ProviderError("API request failed")
        return data

    async def async_balance(self, today=None):
        today = today or date.today()
        balance = await self._read("/balance")
        tariff = history = None
        # Optional endpoints must not hide a valid account balance on failure.
        try:
            tariff = await self._read("/tariff")
        except (aiohttp.ClientError, TimeoutError, ProviderError):
            pass
        try:
            history = await self._read(
                "/statistics",
                params={
                    "type": 0,
                    "startDate": f"{today:%Y-%m}-01 00:00:00",
                    "endDate": f"{today:%Y-%m-%d} 23:59:59",
                },
            )
        except (aiohttp.ClientError, TimeoutError, ProviderError):
            pass
        return parse_account(balance, tariff, history, today)


def money(value):
    """Strict finite numeric JSON values; missing values never become zero."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def forecast_date(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        # Preserve the provider's calendar date; don't shift it through UTC.
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_account(balance, tariff=None, history=None, today=None):
    amount = money(balance.get("balance"))
    if balance.get("success") is not True or amount is None:
        raise ProviderError("Balance missing from API response")
    names = []
    monthly_fee = None
    rows = (
        tariff.get("tariffArray")
        if isinstance(tariff, dict) and tariff.get("success") is True
        else None
    )
    if isinstance(rows, list) and rows and all(isinstance(row, dict) for row in rows):
        names = [
            row["tariffUserName"] for row in rows if isinstance(row.get("tariffUserName"), str)
        ]
        fees = [money(row.get("tariffCost")) for row in rows]
        if all(row.get("tariffTimeUnit") == "MONTHLY" for row in rows) and None not in fees:
            monthly_fee = sum(fees, Decimal(0))
    expenses = None
    events = (
        history.get("eventArray")
        if isinstance(history, dict) and history.get("success") is True
        else None
    )
    if isinstance(events, list):
        total = Decimal(0)
        for event in events:
            if not isinstance(event, dict):
                break
            if event.get("noData"):
                continue
            value = money(event.get("amount"))
            if value is None:
                break
            if value < 0:
                total -= value
        else:
            expenses = total
    # The web UI uses estimateDate only when balanceState is true.
    forecast = (
        forecast_date(balance.get("estimateDate")) if balance.get("balanceState") is True else None
    )
    return AccountBalance(
        amount,
        sufficient_until=forecast,
        minimum_payment=money(balance.get("amountForUnlock")),
        tariff=" / ".join(names) or None,
        monthly_fee=monthly_fee,
        month_expenses=expenses,
        billing_date=today or date.today(),
    )
