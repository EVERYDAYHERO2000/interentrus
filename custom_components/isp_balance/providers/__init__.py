"""Provider clients, independent of Home Assistant."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


class AuthenticationError(Exception):
    """Credentials were rejected."""


class ProviderError(Exception):
    """Provider communication or response format failed."""


@dataclass(frozen=True)
class AccountBalance:
    """Normalized provider response."""

    amount: Decimal
    currency: str = "RUB"
    sufficient_until: date | None = None
    minimum_payment: Decimal | None = None
    tariff: str | None = None
    monthly_fee: Decimal | None = None
    month_expenses: Decimal | None = None
    billing_date: date | None = None


class Provider(Protocol):
    async def async_balance(self) -> AccountBalance:
        """Return current balance, authenticating as necessary."""
        ...
