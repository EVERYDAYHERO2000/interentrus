"""UI setup and credential renewal."""

import hashlib
import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_WARNING_DAYS, DEFAULT_WARNING_DAYS, DOMAIN, PROVIDER_NETNORD
from .providers import AuthenticationError, ProviderError
from .providers.factory import PROVIDER_NAMES, create_client

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        reauth = self.context.get("source") == "reauth"
        if user_input is not None:
            data = dict(user_input)
            data["username"] = data["username"].strip()
            if reauth:
                entry = self._get_reauth_entry()
                data["provider"] = entry.data["provider"]
                data["username"] = entry.data["username"]
            session = async_create_clientsession(self.hass)
            try:
                await create_client(
                    data["provider"], session, data["username"], data["password"]
                ).async_balance()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except ProviderError as err:
                # ProviderError messages are fixed diagnostic strings, never page contents.
                _LOGGER.warning("%s setup response could not be parsed: %s", data["provider"], err)
                errors["base"] = "invalid_response"
            finally:
                session.detach()
            if not errors:
                if reauth:
                    return self.async_update_reload_and_abort(entry, data_updates=data)
                identity = hashlib.sha256(data["username"].encode()).hexdigest()
                await self.async_set_unique_id(f"{data['provider']}_{identity}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{PROVIDER_NAMES[data['provider']]} {data['username']}", data=data
                )
        fields = {}
        if not reauth:
            fields[vol.Required("provider", default=PROVIDER_NETNORD)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": key, "label": name} for key, name in PROVIDER_NAMES.items()]
                )
            )
            fields[vol.Required("username")] = str
        else:
            # Keep account identity fixed during credential renewal.
            fields[vol.Required("username", default=self._get_reauth_entry().data["username"])] = (
                str
            )
        fields[vol.Required("password")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        )
        return self.async_show_form(step_id="user", data_schema=vol.Schema(fields), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_user()


class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_WARNING_DAYS,
                        default=self.config_entry.options.get(
                            CONF_WARNING_DAYS, DEFAULT_WARNING_DAYS
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=365))
                }
            ),
        )
