"""
Support for Enigma2 set-top boxes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/enigma/
"""
#
# For more details,
# please refer to github at
# https://github.com/cinzas/homeassistant-enigma-player
#
#
# imports and dependencies
import asyncio
import aiohttp
from aiohttp.client_exceptions import ClientError
from urllib.error import HTTPError, URLError
import urllib.parse
import urllib.request

import voluptuous as vol

from custom_components.enigma import (
    _LOGGER, DEFAULT_NAME, DEFAULT_PASSWORD,
    DEFAULT_PORT, DEFAULT_USERNAME)
from homeassistant.components.notify import (
    ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME)
from homeassistant.helpers import aiohttp_client, config_validation as cv


# VERSION
VERSION = '1.9.1'

# Default value for display (if not passed as argument in data field)
# 20 seconds for timeout
DEFAULT_DISPLAY_TIME = '20'
# Message type
# 0 -> Yes/No
# 1 -> Info
# 2 -> Message
# 3 -> Attention
DEFAULT_MESSAGE_TYPE = '2'

# Get configs
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def get_service(hass, config, discovery_info=None):
    """Initialize the enigma notify service."""
    if config.get(CONF_HOST) is not None:
        _LOGGER.info("[Enigma Notify] Adding Enigma receiver at host %s initialized",
                     config.get(CONF_HOST))
        # Opener for http connection
        session = aiohttp_client.async_get_clientsession(hass)
        enigma = EnigmaNotify(config.get(CONF_HOST),
                              config.get(CONF_PORT),
                              config.get(CONF_NAME),
                              config.get(CONF_USERNAME),
                              config.get(CONF_PASSWORD),
                              session)
        _LOGGER.info("[Enigma Notify] Added Enigma receiver at host %s initialized",
                     config.get(CONF_HOST))
    return enigma


class EnigmaNotify(BaseNotificationService):
    """Representation of a notification service for Enigma device."""

    def __init__(self, host, port, name, username, password, opener):
        """Initialize the Enigma device."""
        self._host = host
        self._port = port
        self._name = name
        self._username = username
        self._password = password
        # self._opener = aiohttp.ClientSession()
        self._opener = opener

    # Async API requests
    async def request_call(self, url):
        """Call web API request."""
        uri = 'http://' + self._host + ":" + str(self._port) + url
        _LOGGER.debug("[Enigma Notify]: [request_call] - Call request %s ", uri)
        try:
            # Check if is password enabled
            if self._password is not None:
                # Handle HTTP Auth
                async with self._opener.get(uri, auth=aiohttp.BasicAuth(self._username, self._password)) as resp:
                    text = await resp.read()
                    return text
            else:
                async with self._opener.get(uri) as resp:
                    text = await resp.read()
                    return text
        except:
            _LOGGER.exception("[Enigma Notify]: [request_call] - Error connecting to \
                              remote enigma")

    async def async_send_message(self, message="", **kwargs):
        """Send message."""
        try:
            displaytime = DEFAULT_DISPLAY_TIME
            messagetype = DEFAULT_MESSAGE_TYPE
            data = kwargs.get(ATTR_DATA) or {}
            if data:
                if 'displaytime' in data:
                    displaytime = data['displaytime']
                if 'messagetype' in data:
                    messagetype = data['messagetype']

            _LOGGER.debug("Enigma notify service: [async_send_message] - Sending Message %s \
                          (timeout=%s and type=%s", message, displaytime,
                          messagetype)
            await self.request_call('/web/message?text=' +
                              message.replace(" ", "%20") + '&type=' +
                              messagetype + '&timeout=' + displaytime)
        except ImportError:
            _LOGGER.error("Enigma notify service: [Exception raised]")
