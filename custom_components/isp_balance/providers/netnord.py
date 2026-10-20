"""Netnord login protocol observed on the public cabinet form.

Balance extraction follows the authenticated sidebar structure.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import aiohttp
from bs4 import BeautifulSoup

from . import AccountBalance, AuthenticationError, ProviderError

BASE_URL = "https://cabinet.net-nord.ru"
WELCOME_URL = f"{BASE_URL}/cabinet/welcome/"
ACCOUNT_URL = f"{BASE_URL}/cabinet/Лицевой-счет/"


class LoginForm(HTMLParser):
    """Read tokens only from the form containing LOGIN and PASSWD."""

    def __init__(self, html: str) -> None:
        super().__init__()
        self.forms: list[tuple[dict, dict]] = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = (attrs, {})
        elif tag == "input" and self.current is not None:
            if name := attrs.get("name"):
                self.current[1][name] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None

    def credentials_form(self):
        for attrs, fields in self.forms:
            if "LOGIN" in fields and "PASSWD" in fields:
                return attrs, fields
        return None


class NetnordClient:
    """Use a dedicated session to isolate account cookies."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        self.session = session
        self.username = username
        self.password = password

    async def _request(self, method: str, url: str, **kwargs) -> str:
        # Do not send credentials or cookies through an unexpected redirect.
        for _ in range(5):
            if urlsplit(url)[:2] != urlsplit(BASE_URL)[:2]:
                raise ProviderError("Unexpected cabinet destination")
            async with self.session.request(
                method,
                url,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=30),
                **kwargs,
            ) as response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise ProviderError("Missing redirect location")
                    url = urljoin(url, location)
                    if response.status == 303 or (
                        response.status in (301, 302) and method == "POST"
                    ):
                        method, kwargs = "GET", {}
                    continue
                response.raise_for_status()
                return await response.text()
        raise ProviderError("Too many cabinet redirects")

    async def async_login(self) -> str:
        html = await self._request("GET", WELCOME_URL)
        form = LoginForm(html).credentials_form()
        if form is None:
            return html
        attrs, fields = form
        if not all(fields.get(key) for key in ("module_token", "module_token_unique")):
            raise ProviderError("Login form tokens missing")
        payload = {key: fields[key] for key in ("module_token", "module_token_unique")}
        payload.update(LOGIN=self.username, PASSWD=self.password)
        html = await self._request(
            "POST", urljoin(WELCOME_URL, attrs.get("action", "")), data=payload
        )
        if LoginForm(html).credentials_form() is not None:
            raise AuthenticationError("Cabinet still displays the login form")
        return html

    async def async_balance(self, today: date | None = None) -> AccountBalance:
        """Read balance, signing in again if the session expired."""
        html = await self._request("GET", ACCOUNT_URL)
        if LoginForm(html).credentials_form() is not None:
            await self.async_login()
            html = await self._request("GET", ACCOUNT_URL)
            if LoginForm(html).credentials_form() is not None:
                raise AuthenticationError("Cabinet session was not established")
        return parse_balance(html, today=today)


def parse_balance(html: str, today: date | None = None) -> AccountBalance:
    """Extract the amount associated with Баланс ЛС, never minimum payment."""
    soup = BeautifulSoup(html, "html.parser")
    amounts = []
    sufficient_until = None
    for header in soup.select(".carbon_modules_userinfosidebar .sidebar-block-header"):
        if " ".join(header.stripped_strings).strip().rstrip(":").casefold() != "баланс лс":
            continue
        data = header.find_next_sibling()
        if data is None or "user-data" not in data.get("class", []):
            raise ProviderError("Balance block missing")
        # The provider emits empty paragraphs before the monetary amount.
        paragraphs = [p.get_text(" ", strip=True) for p in data.find_all("p", recursive=False)]
        text = next((text for text in paragraphs if text), "")
        text = text.replace("\xa0", " ").replace("\u202f", " ").replace("−", "-")
        if not re.fullmatch(r"[+-]?\d+(?: \d{3})*(?:[,.]\d{1,2})?", text):
            raise ProviderError("Unrecognized balance amount")
        amounts.append(Decimal(text.replace(" ", "").replace(",", ".")))
        forecast = data.get_text(" ", strip=True)
        match = re.search(r"Хватит\s+до\s+(\d{2}\.\d{2}\.\d{4})(?!\d)", forecast, re.IGNORECASE)
        if match:
            try:
                sufficient_until = datetime.strptime(match[1], "%d.%m.%Y").date()
            except ValueError:
                # A broken forecast must not discard a valid monetary balance.
                sufficient_until = None
    if len(amounts) != 1:
        raise ProviderError("Balance block missing or ambiguous")
    minimum_payment = None
    for header in soup.select(".carbon_modules_userinfosidebar .sidebar-block-header"):
        if header.get_text(" ", strip=True).rstrip(":").casefold() == "мин. платеж":
            data = header.find_next_sibling()
            if data is not None and "user-data" in data.get("class", []):
                values = [p.get_text(" ", strip=True) for p in data.find_all("p", recursive=False)]
                minimum_payment = parse_money(next((v for v in values if v), ""))
    tariff = monthly_fee = None
    for row in soup.select(".carbon_modules_abonentstatus tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 2 and cells[0].get_text(strip=True) == "Тариф":
            text = cells[1].get_text(" ", strip=True)
            match = re.fullmatch(r"(.+?):\s*([\d ,.\xa0\u202f]+)\s*руб\.\s*/\s*мес\.", text)
            if match:
                tariff = match[1].strip().strip('"«»')
                monthly_fee = parse_money(match[2].strip())
            else:
                tariff = text or None
    expenses = []
    expense_block = soup.select_one(".carbon_modules_currentmonthexpenses")
    if expense_block is not None:
        for row in expense_block.select("tr"):
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue
            if len(cells) != 2 or (value := parse_money(cells[1].get_text(strip=True))) is None:
                expenses = [None]
                break
            expenses.append(value)
    month_expenses = sum(expenses, Decimal(0)) if expenses and None not in expenses else None
    return AccountBalance(
        amounts[0],
        sufficient_until=sufficient_until,
        minimum_payment=minimum_payment,
        tariff=tariff,
        monthly_fee=monthly_fee,
        month_expenses=month_expenses,
        billing_date=today or date.today(),
    )


def parse_money(text: str) -> Decimal | None:
    """Parse an optional monetary field without confusing missing data with zero."""
    text = text.replace("\xa0", " ").replace("\u202f", " ").replace("−", "-").strip()
    if not re.fullmatch(r"[+-]?\d+(?: \d{3})*(?:[,.]\d{1,2})?", text):
        return None
    return Decimal(text.replace(" ", "").replace(",", "."))
