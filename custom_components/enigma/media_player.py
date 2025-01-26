"""
Support for Enigma2 set-top boxes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/enigma/
"""
#
# For more details, please refer to github at
# https://github.com/cinzas/homeassistant-enigma-player
#
# This is a branch from
# https://github.com/KavajNaruj/homeassistant-enigma-player
#

# Imports and dependencies
import asyncio
from datetime import timedelta
from urllib.error import HTTPError, URLError
import urllib.parse
import urllib.request
import aiohttp
import voluptuous as vol
from datetime import timedelta
from urllib.error import HTTPError, URLError

# From homeassitant

from custom_components.enigma import _LOGGER, DOMAIN as ENIGMA_DOMAIN

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType
)

from homeassistant.const import (
    STATE_OFF, 
    STATE_ON, 
    STATE_UNKNOWN
)

import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

# VERSION
VERSION = '1.9'

# Dependencies
DEPENDENCIES = ['enigma']

# DEFAULTS
DEFAULT_PORT = 80
DEFAULT_NAME = "Enigma2 Satelite"
DEFAULT_TIMEOUT = 30
DEFAULT_USERNAME = 'root'
DEFAULT_PASSWORD = ''
DEFAULT_BOUQUET = ''
DEFAULT_PICON = 'picon'

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=5)

SUPPORT_ENIGMA = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PAUSE
)

MAX_VOLUME = 100

# SETUP PLATFORM
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up platform."""                         
    """Initialize the Enigma device."""
    devices = []
    enigma_list = hass.data[ENIGMA_DOMAIN]

    for device in enigma_list:
        _LOGGER.debug("Configured a new EnigmaMediaPlayer %s",
                      device.get_host)
        devices.append(EnigmaMediaPlayer(device))

    async_add_entities(devices, update_before_add=True)


# Enigma Media Player Device
class EnigmaMediaPlayer(MediaPlayerEntity):
    """Representation of a Enigma Media Player device."""

    def __init__(self, EnigmaMediaPlayerEntity):
        """Initialize the Enigma device."""
        self._host = EnigmaMediaPlayerEntity.get_host
        self._port = EnigmaMediaPlayerEntity.get_port
        self._name = EnigmaMediaPlayerEntity.get_name
        self._username = EnigmaMediaPlayerEntity.get_username
        self._password = EnigmaMediaPlayerEntity.get_password
        self._timeout = EnigmaMediaPlayerEntity.get_timeout
        self._bouquet = EnigmaMediaPlayerEntity.get_bouquet
        self._picon = EnigmaMediaPlayerEntity.get_picon
        self._opener = EnigmaMediaPlayerEntity.get_opener
        self._pwstate = 'true'
        self._volume = 0
        self._muted = False
        self._selected_source = ''
        self._selected_media_content_id = ''
        self._selected_media_title = ''
        self._picon_url = None
        self._source_names = {}
        self._sources = {}

    # Run when added to HASS TO LOAD SOURCES
    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
      
    # Load channels from specified bouquet or from first available bouquet
    async def load_sources(self):
        """Initialize the Enigma device loading the sources."""
        from bs4 import BeautifulSoup
        if self._bouquet:
            # Load user set bouquet.
            _LOGGER.debug("Enigma: [load_sources] - Request user bouquet %s ",
                          self._bouquet)
            epgbouquet_xml = await self.request_call('/web/epgnow?bRef=' +
                                               urllib.parse.quote_plus
                                               (self._bouquet))

            # Channels name
            soup = BeautifulSoup(epgbouquet_xml, features = "xml")
            src_names = soup.find_all('e2eventservicename')
            self._source_names = [src_name.string for src_name in src_names]
            # Channels reference
            src_references = soup.find_all('e2eventservicereference')
            sources = [src_reference.string for src_reference in
                       src_references]
            self._sources = dict(zip(self._source_names, sources))

        else:
            # Load sources from first bouquet.
            reference = urllib.parse.quote_plus(await self.get_bouquet_reference())
            _LOGGER.debug("Enigma: [load_sources] - Request reference %s ",
                          reference)
            epgbouquet_xml = await self.request_call('/web/epgnow?bRef=' + reference)

            # Channels name
            soup = BeautifulSoup(epgbouquet_xml, features = "xml")
            src_names = soup.find_all('e2eventservicename')
            self._source_names = [src_name.string for src_name in src_names]

            # Channels reference
            src_references = soup.find_all('e2eventservicereference')
            sources = [src_reference.string for src_reference in
                       src_references]
            self._sources = dict(zip(self._source_names, sources))

    async def get_bouquet_reference(self):
        """Import BeautifulSoup."""
        from bs4 import BeautifulSoup
        # Get first bouquet reference
        bouquets_xml = await self.request_call('/web/getallservices')
        soup = BeautifulSoup(bouquets_xml, features = "xml")
        return soup.find('e2servicereference').renderContents().decode('UTF8')

    # Async API requests
    async def request_call(self, url):
        """Call web API request."""
        uri = 'http://' + self._host + ":" + str(self._port) + url
        emptyxml = '<root></root>'
        _LOGGER.debug("Enigma: [request_call] - Call request %s ", uri)
        try:
            # Check if is password enabled
            if self._password is not None:
                # Handle HTTP Auth
                async with self._opener.get(uri, auth=aiohttp.BasicAuth(self._username, self._password), timeout=5) as resp:
                    text = await resp.read()
                    return text
            else:
                async with self._opener.get(uri) as resp:
                    text = await resp.read()
                    return text
        except:
            # return to bs4
            return emptyxml

    # Component Update
    @Throttle(MIN_TIME_BETWEEN_SCANS)
    async def async_update(self):
        """Import BeautifulSoup."""
        from bs4 import BeautifulSoup
        # Get the latest details from the device.
        _LOGGER.debug("Enigma: [update] - request for host %s (%s)", self._host,
                     self._name)
        powerstate_xml = await self.request_call('/web/powerstate')
        powerstate_soup = BeautifulSoup(powerstate_xml, features = "xml")
        try:
            pwstate = powerstate_soup.find('e2instandby').renderContents().decode('UTF8').strip()
        except:
            pwstate = 'true' # true means box is in standby/offline

        _LOGGER.debug("Enigma: [update] - Powerstate for host %s = %s previous state = %s",
                      self._host, pwstate, self._pwstate)

        if pwstate == 'false' and self._pwstate == 'true':
            _LOGGER.debug("Enigma: [update] - Powerstate change detected (is now online), reloading sources")
            await self.load_sources()

        if pwstate.find('false') >= 0:
            self._pwstate = 'false'

        if pwstate.find('true') >= 0:
            self._pwstate = 'true'

        # If name was not defined, get the name from the box
        if self._name == 'Enigma2 Satelite':
            about_xml = await self.request_call('/web/about')
            soup = BeautifulSoup(about_xml, features = "xml")
            name = soup.e2model.renderContents().decode('UTF8')
            _LOGGER.debug("Enigma: [update] - Name for host %s = %s",
                          self._host, name)
            if name:
                self._name = name

        # If powered on
        if self._pwstate == 'false':
            subservices_xml = await self.request_call('/web/subservices')
            soup = BeautifulSoup(subservices_xml, features = "xml")
            servicename = soup.e2servicename.renderContents().decode('UTF8')
            reference = soup.e2servicereference.renderContents().decode('UTF8')
            eventid = 'N/A'
            eventtitle = 'N/A'
            # If we got a valid reference, check the title of the event and
            # the picon url
            if reference != '' and reference != 'N/A' and \
                            not reference.startswith('1:0:0:0:0:0:0:0:0:0:'):
                xml = await self.request_call('/web/epgservicenow?sRef=' + reference)
                soup = BeautifulSoup(xml, features = "xml")
                eventtitle = soup.e2eventtitle.renderContents().decode('UTF8')
                eventid = soup.e2eventid.renderContents().decode('UTF8')
                if self._password != DEFAULT_PASSWORD:
                    # If reference has custonam channel name added to the
                    # end, need to remove it
                    if "::" in reference:
                        reference = reference.split("::")[0]+":"
                        
                    # if picon = screenhost then get screenshot
                    if self._picon == 'screenshot':
                        self._picon_url = 'http://' + \
                                           self._username + ':' + \
                                           self._password + \
                                           '@' + self._host + ':' + \
                                           str(self._port) + '/grab?format=png\
                                           &r=720&mode=all&reference=' + \
                                           reference.replace(":", "_")[:-1]
                    # otherwise try to get picon
                    else:
                        self._picon_url = 'http://' + \
                                           self._username + ':' + \
                                           self._password + \
                                           '@' + self._host + ':' + \
                                           str(self._port) + '/picon/' + \
                                           reference.replace(":", "_")[:-1] \
                                           + '.png'
                else:
                    # if icon = screenhost then get screenshot
                    if self._picon == 'screenshot':
                        self._picon_url = 'http://' + \
                                           self._username + ':' + \
                                           self._password + \
                                           '@' + self._host + ':' + \
                                           str(self._port) + '/grab?format=png\
                                           &r=720&mode=all&reference=' + \
                                           reference.replace(":", "_")[:-1]
                    # otherwise try to get picon
                    else:
                        self._picon_url = 'http://' + self._host + ':' + \
                                           str(self._port) + '/picon/' + \
                                           reference.replace(":", "_")[:-1] \
                                           + '.png'
            _LOGGER.debug("Enigma: [update] - Eventtitle for host %s = %s",
                          self._host, eventtitle)

            # Check volume and if is muted and update self variables
            volume_xml = await self.request_call('/web/vol')
            soup = BeautifulSoup(volume_xml, features = "xml")
            volcurrent = soup.e2current.renderContents().decode('UTF8')
            volmuted = soup.e2ismuted.renderContents().decode('UTF8')

            self._volume = int(volcurrent) / MAX_VOLUME if volcurrent else None
            self._muted = (volmuted == 'True') if volmuted else None
            _LOGGER.debug("Enigma: [update] - Volume for host %s = %s",
                          self._host, volcurrent)
            _LOGGER.debug("Enigma: [update] - Is host %s muted = %s",
                          self._host, volmuted)

            # Info of selected source and title
            self._selected_source = servicename 
            self._selected_media_content_id = eventid
            self._selected_media_title = servicename + ' - ' + eventtitle
        return True

# GET - Name
    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return str(self._host).replace(".", "_")+"_"+str(self._port)+"_"+str(self._name)

# GET - State
    @property
    def state(self):
        """Return the state of the device."""
        if self._pwstate == 'true':
            return STATE_OFF
        if self._pwstate == 'false':
            return STATE_ON

        return STATE_UNKNOWN

# GET - Volume Level
    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

# GET - Muted
    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

# GET - Features
    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_ENIGMA

# GET - Content type
    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MediaType.TVSHOW

# GET - Content id - Current Channel name
    @property
    def media_content_id(self):
        """Service Ref of current playing media."""
        return self._selected_media_content_id

# GET - Media title - Current Channel name
    @property
    def media_title(self):
        """Title of current playing media."""
        return self._selected_media_title

# GET - Content picon - Current Channel Picon
# /picon directory must exist in enigma2 box (use symlink if not)
    @property
    def media_image_url(self):
        """Title of current playing media."""
        _LOGGER.debug("Enigma: [media_image_url] - %s", self._picon_url)
        return self._picon_url

# GET - Current channel - Current Channel Name
    @property
    def source(self):
        """Return the current input source."""
        return self._selected_source

# GET - Channel list - Channel names from current bouquet
    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

# SET - Change channel - From dropbox menu
    async def async_select_source(self, source):
        """Select input source."""
        _LOGGER.debug("Enigma: [async_select_source] - Change source channel")
        await self.request_call('/web/zap?sRef=' + self._sources[source])

# SET - Volume up
    async def async_volume_up(self):
        """Set volume level up."""
        await self.request_call('/web/vol?set=up')

# SET - Volume down
    async def async_volume_down(self):
        """Set volume level down."""
        await self.request_call('/web/vol?set=down')

# SET - Volume level
    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volset = str(round(volume * MAX_VOLUME))
        await self.request_call('/web/vol?set=set' + volset)

# SET - Volume mute
    async def async_mute_volume(self, mute):
        """Mute or unmute media player."""
        await self.request_call('/web/vol?set=mute')

# SET - Media Play/pause
    async def async_media_play_pause(self):
        """Simulate play pause media player."""
        _LOGGER.debug("Enigma: [play_pause_toogle] - Does nothing")

# SET - Media Play
    async def async_media_play(self):
        """Send play command."""
        _LOGGER.debug("Enigma: [play] - Does nothing")

# SET - Media Pause
    async def async_media_pause(self):
        """Send media pause command to media player."""
        _LOGGER.debug("Enigma: [pause] - Does nothing")


# SET - Change to channel number
    async def async_play_media(self, media_type, media_id, **kwargs):
        """Support changing a channel."""
        if media_type != MediaType.CHANNEL:
            _LOGGER.error('Unsupported media type')
            return
        try:
            cv.positive_int(media_id)
        except vol.Invalid:
            _LOGGER.error('Media ID must be positive integer')
            return
        # Hack to map remote key press
        # 2   Key "1"
        # 3   Key "2"
        # 4   Key "3"
        # 5   Key "4"
        # 6   Key "5"
        # 7   Key "6"
        # 8   Key "7"
        # 9   Key "8"
        # 10  Key "9"
        # 11  Key "0"
        for digit in media_id:
            if digit == '0':
                channel_digit = '11'
            else:
                channel_digit = int(digit)+1
            await self.request_call('/web/remotecontrol?command='+str(channel_digit))

# SET - Turn on
    async def async_turn_on(self):
        """Turn the media player on."""
        await self.request_call('/web/powerstate?newstate=4')
        self.async_update()

# SET - Turn of
    async def async_turn_off(self):
        """Turn off media player."""
        await self.request_call('/web/powerstate?newstate=5')

# SET - Next channel
    async def async_media_next_track(self):
        """Change to next channel."""
        await self.request_call('/web/remotecontrol?command=106')

# SET - Previous channel
    async def async_media_previous_track(self):
        """Change to previous channel."""
        await self.request_call('/web/remotecontrol?command=105')
