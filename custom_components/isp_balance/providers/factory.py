"""Select a provider without coupling its protocol to the HA UI."""

from ..const import PROVIDER_MICRON, PROVIDER_NETNORD
from . import ProviderError
from .micron import MicronClient
from .netnord import NetnordClient

PROVIDER_NAMES = {PROVIDER_NETNORD: "Нетнорд", PROVIDER_MICRON: "Микронмедиа"}


def create_client(provider, session, username, password):
    clients = {PROVIDER_NETNORD: NetnordClient, PROVIDER_MICRON: MicronClient}
    if provider not in clients:
        raise ProviderError("Unsupported provider")
    return clients[provider](session, username, password)
