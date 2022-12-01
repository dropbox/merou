import logging
import os
import subprocess
import time
from subprocess import CalledProcessError
from typing import TYPE_CHECKING
from urllib.parse import ParseResult, urlparse

import pytz
import yaml

if TYPE_CHECKING:
    from pytz import BaseTzInfo
    from typing import List, Optional

# TODO(rra): Desire for a single global settings object is currently deeply embedded.  The rewrite
# to hexagonal architecture is probably required before we can fully eliminate it.
_GLOBAL_SETTINGS_OBJECT = None  # type: Optional[Settings]


def default_settings_path():
    # type: () -> str
    return os.environ.get("GROUPER_SETTINGS", "/etc/grouper.yaml")


class DatabaseSourceException(Exception):
    """Raised if the database_source program repeatedly fails."""

    pass


class InvalidSettingsError(Exception):
    """Raised if configuration settings are invalid."""

    pass


class Settings:
    """Grouper configuration settings.

    Provides a parent class for settings objects, machinery for reading settings from the YAML
    configuration file, and defaults for base settings that apply regardless of application.  Each
    Grouper application with its own settings will subclass this class and add additional default
    values and configuration of what sections of the settings file to load.
    """

    # If running the database_source command fails, retry up to DB_URL_RETRIES times, pausing
    # DB_URL_RETRY_DELAY seconds between attempt.
    DB_URL_RETRIES = 3
    DB_URL_RETRY_DELAY = 1

    @staticmethod
    def global_settings_from_config(filename=None, section=None):
        # type: (Optional[str], Optional[str]) -> Settings
        """Create and return a new global Settings singleton.

        Create a new Settings object, load the specified configuration file, and then set it as the
        global singleton Settings object.  This static method is currently required because so much
        of the code assumes a globally-accessible Settings object rather than passing Settings in
        to functions that need it.  Once Settings is injected everywhere, this will be deleted.
        """
        settings = Settings()
        settings.update_from_config(filename, section)
        set_global_settings(settings)
        return settings

    def __init__(self):
        # type: () -> None
        """Set up base defaults."""
        self._logger = logging.getLogger(__name__)

        # Keep attributes here in the same order as in config/dev.yaml.
        self.auditors_group = ""
        self.database = ""
        self.database_source = ""
        self.date_format = "%Y-%m-%d %I:%M %p"
        self.expiration_notice_days = 7
        self.github_app_client_id = None  # type: Optional[str]
        self.http_proxy_host = None  # type: Optional[str]
        self.http_proxy_port = None  # type: Optional[int]
        self.log_format = "%(asctime)-15s\t%(levelname)s\t%(message)s  [%(name)s]"
        self.plugin_dirs = []  # type: List[str]
        self.plugin_module_paths = []  # type: List[str]
        self.restricted_ownership_permissions = []  # type: List[str]
        self.send_emails = True
        self.smtp_server = "localhost"
        self.smtp_use_ssl = False
        self.smtp_username = ""
        self.smtp_password = ""
        self.from_addr = "no-reply@grouper.local"
        self.service_account_email_domain = "svc.localhost"
        self.timezone = "UTC"  # type: ignore[assignment]  # mypy/issues/3004
        self.url = "http://127.0.0.1:8888"
        self.user_auth_header = "X-Grouper-User"

    @property
    def database(self):
        # type: () -> str
        """Return the configured database URL.

        If database is set in the config file or directly on the Settings object, it is the static
        URL.  Otherwise, database_source must be set and be the path to a program that will be run
        to determine the database URL.

        The database_source program will be run every time the database attribute is accessed.
        Caching doesn't seem worthwhile given that it is only accessed during process startup, on
        each loop of a periodic background thread, or after a database error.
        """
        if self._database:
            return self._database
        elif not self.database_source:
            raise InvalidSettingsError("Settings not initialized from a configuration file")
        return self._database_source_output()

    @database.setter
    def database(self, url):
        # type: (str) -> None
        self._database = url

    @property
    def timezone(self):
        # type: () -> BaseTzInfo
        return self._timezone

    @timezone.setter
    def timezone(self, timezone):
        # type: (str) -> None
        self._timezone = pytz.timezone(timezone)

    def update_from_config(self, filename=None, section=None):
        # type: (Optional[str], Optional[str]) -> None
        """Load configuration information from a file and update settings.

        The file will be parsed as YAML.  By default, the common section will be loaded.  If any
        additional section was specified as a parameter, that section will also be loaded, after
        the common section.

        Only settings that match an existing attribute in the Settings object will be updated.
        Other settings in the configuration file will be silently ignored (well, with a debug log
        message).
        """
        if not filename:
            filename = default_settings_path()
        self._logger.debug("Loading %s", filename)
        with open(filename) as config:
            data = yaml.safe_load(config)
        settings = data.get("common", {})
        if section:
            settings.update(data.get(section, {}))

        # Update the stored attributes from the configuration file, skipping any setting that
        # doesn't correspond to an attribute on the settings object.  The check special-cases the
        # database key because hasattr appears to run the property method, which may throw an
        # exception.
        for key, value in settings.items():
            key = key.lower()
            if key.startswith("_"):
                self._logger.warning("Ignoring invalid setting %s", key)
            elif not (key == "database" or hasattr(self, key)):
                self._logger.debug("Ignoring unknown setting %s", key)
            else:
                setattr(self, key, value)

        # Ensure the settings are valid.
        if not self._database and not self.database_source:
            msg = "Neither database nor database_source are set in {}".format(filename)
            raise InvalidSettingsError(msg)

    def _database_source_output(self):
        # type: () -> str
        """Run the database_source command to get a new database URL."""
        retry = 0
        while True:
            try:
                self._logger.debug("Getting database URL by running %s", self.database_source)
                raw_url = subprocess.check_output([self.database_source], stderr=subprocess.STDOUT)
                url = raw_url.decode().strip()
                if not url:
                    raise DatabaseSourceException("Returned URL is empty")
                self._logger.debug(
                    "New database configuration is %s", self._db_connection_info(url)
                )
                return url
            except (UnicodeDecodeError, DatabaseSourceException, CalledProcessError) as e:
                self._logger.exception("Running %s failed", self.database_source)
                retry += 1
                if retry < self.DB_URL_RETRIES:
                    self._logger.warning("Retrying after %ds", self.DB_URL_RETRY_DELAY)
                    time.sleep(self.DB_URL_RETRY_DELAY)
                else:
                    msg = "Unable to get a database URL from {} after {} tries: {}".format(
                        self.database_source, self.DB_URL_RETRIES, str(e)
                    )
                    raise DatabaseSourceException(msg)

    def _db_connection_info(self, url):
        # type: (str) -> ParseResult
        """Parse a URL and remove any password, returning a version suitable for logging."""
        parsed_url = urlparse(url)

        if parsed_url.password is None:
            netloc = parsed_url.netloc
        else:
            host = parsed_url.netloc.rsplit("@", 1)[-1]
            netloc = f"{parsed_url.username}:<REDACTED>@{host}"

        return parsed_url._replace(netloc=netloc)


def settings():
    # type: () -> Settings
    assert _GLOBAL_SETTINGS_OBJECT, "Global Settings object not initialized"
    return _GLOBAL_SETTINGS_OBJECT


def set_global_settings(settings):
    # type: (Settings) -> None
    """Set the global settings object with another one.

    This is a horrible hack forced by the use of global singletons for settings, instead of passing
    around a proper object.

    Each component of Grouper subclasses the global settings object to add its own settings.
    However, some generic code in Grouper wants to load the current settings object, and may run in
    multiple components.  We therefore need to set a global singleton after the component has
    initialized it from a configuration file, and then use it in all other code.
    """
    global _GLOBAL_SETTINGS_OBJECT
    _GLOBAL_SETTINGS_OBJECT = settings
