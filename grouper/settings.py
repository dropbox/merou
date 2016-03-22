import os
import logging
import threading
import time
import yaml

from expvar.stats import stats


class Settings(object):
    def __init__(self, initial_settings):
        self.settings = initial_settings
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self._loading_thread_started = False

    @classmethod
    def from_settings(cls, settings, initial_settings=None):
        _settings = {}
        _settings.update(settings.settings)
        if initial_settings:
            _settings.update(initial_settings)
        return cls(_settings)

    def _update_from_config(self, filename, section=None):
        self.logger.info("Loading " + filename)
        with open(filename) as config:
            data = yaml.safe_load(config.read())

        settings = {}
        settings.update(data.get("common", {}))
        if section:
            settings.update(data.get(section, {}))

        for key, value in settings.iteritems():
            key = key.lower()

            # Limit the parts of the config file that can have an effect.
            if key not in self.settings:
                continue

            override = getattr(self, "override_%s" % key, None)
            if override is not None and callable(override):
                value = override(value)

            self[key] = value

    def start_config_thread(self, filename, section=None, refresh_config_seconds=10):
        """
        Start a daemon thread to reload the given config file and section periodically.
        Load the config once before returning.  This function must be called at
        most once.
        """
        assert not self._loading_thread_started, "start_config_thread called twice!"
        self._update_from_config(filename, section=section)

        def refresh_config_loop():
            while True:
                time.sleep(refresh_config_seconds)
                try:
                    self._update_from_config(filename, section=section)
                    stats.set_gauge("successful-config-update", 1)
                except (IOError, yaml.parser.ParserError):
                    stats.set_gauge("successful-config-update", 0)
        thread = threading.Thread(target=refresh_config_loop)
        thread.daemon = True
        thread.start()
        self._loading_thread_started = True

    def __setitem__(self, key, value):
        with self.lock:
            self.settings[key] = value

    def __getitem__(self, key):
        with self.lock:
            return self.settings[key]

    def __getattr__(self, name):
        with self.lock:
            try:
                return self.settings[name]
            except KeyError as err:
                raise AttributeError(err)


def default_settings_path():
    return os.environ.get("GROUPER_SETTINGS", "/etc/grouper.yaml")

settings = Settings({
    "database": None,
    "database_source": None,
    "expiration_notice_days": 7,
    "from_addr": "no-reply@grouper.local",
    "log_format": "%(asctime)-15s\t%(levelname)s\t%(message)s",
    "oneoff_dir": None,
    "plugin_dir": None,
    "restricted_ownership_permissions": None,
    "send_emails": True,
    "sentry_dsn": None,
    "smtp_server": "localhost",
    "url": "http://127.0.0.1:8888",
})
