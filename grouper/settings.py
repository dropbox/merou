import logging
import os
from typing import TYPE_CHECKING

import pytz
import yaml
from six import iteritems

if TYPE_CHECKING:
    from pytz import BaseTzInfo
    from typing import List, Optional

# TODO(rra): Desire for a single global settings object is currently deeply embedded.  The rewrite
# to hexagonal architecture is probably required before we can fully eliminate it.
_GLOBAL_SETTINGS_OBJECT = None


def default_settings_path():
    # type: () -> str
    return os.environ.get("GROUPER_SETTINGS", "/etc/grouper.yaml")


class Settings(object):
    """Grouper configuration settings.

    Provides a parent class for settings objects, machinery for reading settings from the YAML
    configuration file, and defaults for base settings that apply regardless of application.  Each
    Grouper application with its own settings will subclass this class and add additional default
    values and configuration of what sections of the settings file to load.
    """

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
        self.log_format = "%(asctime)-15s\t%(levelname)s\t%(message)s  [%(name)s]"
        self.nonauditor_expiration_days = 5
        self.plugin_dirs = []  # type: List[str]
        self.plugin_module_paths = []  # type: List[str]
        self.restricted_ownership_permissions = []  # type: List[str]
        self.send_emails = True
        self.smtp_server = "localhost"
        self.smtp_use_ssl = False
        self.smtp_username = ""
        self.smtp_password = ""
        self.from_addr = "no-reply@grouper.local"
        self.sentry_dsn = None
        self.service_account_email_domain = "svc.localhost"
        self.timezone = "UTC"
        self.url = "http://127.0.0.1:8888"

        # Hide this with a leading underscore so that the configuration can't mess with it.
        self._timezone_object = pytz.timezone("UTC")

    @property
    def timezone_object(self):
        # type: () -> BaseTzInfo
        return self._timezone_object

    def update_from_config(self, filename=None, section=None):
        # type: (str, Optional[str]) -> None
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
        # doesn't correspond to an attribute on the settings object.  Update the timezone object if
        # needed.
        for key, value in iteritems(settings):
            key = key.lower()
            if key.startswith("_"):
                self._logger.warning("Ignoring invalid setting %s", key)
                continue
            if not hasattr(self, key):
                self._logger.debug("Ignoring unknown setting %s", key)
                continue
            setattr(self, key, value)
            if key == "timezone":
                self._timezone_object = pytz.timezone(self.timezone)


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
