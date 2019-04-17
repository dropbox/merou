import subprocess
from typing import TYPE_CHECKING

import pytest
import pytz
from mock import call, patch

from grouper.settings import DatabaseSourceException, InvalidSettingsError, Settings

if TYPE_CHECKING:
    from py.path import LocalPath

# Data to test loading settings from different sections.
CONFIG_SECTIONS = """
common:
  database: foo

other:
  database: bar
"""

# Data to test ignoring unknown and internal settings.
CONFIG_BOGUS = """
common:
    _logger: bar
    foo: bar
    timezone_object: UTC
    database_url: blah
"""


def test_update_from_config(tmpdir):
    # type: (LocalPath) -> None
    settings = Settings()
    assert not settings.database

    # Create a config file that sets database to different values in different sections.
    config_path = str(tmpdir.join("test.yaml"))
    with open(config_path, "w") as config:
        config.write(CONFIG_SECTIONS)

    # Default loading should only see the common section, but another can be specified.
    settings.update_from_config(config_path)
    assert settings.database == "foo"
    settings.update_from_config(config_path, section="other")
    assert settings.database == "bar"

    # The special timezone_object attribute should be initialized and kept in sync.
    assert settings.timezone_object == pytz.timezone("UTC")
    with open(config_path, "w") as config:
        config.write("common:\n  timezone: US/Pacific\n")
    settings.update_from_config(config_path)
    assert settings.timezone_object == pytz.timezone("US/Pacific")

    # Create a config file that tries to set unknown or internal attributes.
    with open(config_path, "w") as config:
        config.write(CONFIG_BOGUS)
    settings.update_from_config(config_path)
    assert settings._logger != "bar"
    assert not hasattr(settings, "foo")
    assert settings.timezone_object == pytz.timezone("US/Pacific")
    assert settings.database_url == "bar"


def test_database_url():
    # type: () -> None
    settings = Settings()

    # The default is uninitialized and should throw an error until we load a configuration.
    with pytest.raises(InvalidSettingsError):
        assert settings.database_url

    # If database is set, it should be used.
    settings.database = "sqlite:///grouper.sqlite"
    assert settings.database_url == "sqlite:///grouper.sqlite"
    settings.database_source = "/bin/false"
    assert settings.database_url == "sqlite:///grouper.sqlite"

    # If only database_source is set, it should be run to get a URL.
    settings.database = ""
    settings.database_source = "/path/to/program"
    with patch("subprocess.check_output") as mock_subprocess:
        mock_subprocess.return_value = "sqlite:///other.sqlite\n"
        assert settings.database_url == "sqlite:///other.sqlite"
        assert mock_subprocess.call_args_list == [
            call(["/path/to/program"], stderr=subprocess.STDOUT)
        ]

    # If the command fails, it should be retried.  Disable the delay to not make the test slow.
    settings = Settings()
    settings.database_source = "/path/to/program"
    with patch.object(Settings, "DB_URL_RETRY_DELAY", new=0):
        with patch("subprocess.check_output") as mock_subprocess:
            exception = subprocess.CalledProcessError(1, "/path/to/program")
            mock_subprocess.side_effect = [exception, "sqlite:///third.sqlite"]
            assert settings.database_url == "sqlite:///third.sqlite"
            assert mock_subprocess.call_count == 2

    # Commands that return an empty URL should also be retried.
    settings = Settings()
    settings.database_source = "/path/to/program"
    with patch.object(Settings, "DB_URL_RETRY_DELAY", new=0):
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.side_effect = ["", "sqlite:///notempty.sqlite"]
            assert settings.database_url == "sqlite:///notempty.sqlite"
            assert mock_subprocess.call_count == 2

    # Too many retries should raise an exception.
    settings = Settings()
    settings.database_source = "/path/to/program"
    with patch.object(Settings, "DB_URL_RETRY_DELAY", new=0):
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.return_value = ""
            with pytest.raises(DatabaseSourceException):
                assert settings.database_url

    # If the minimum delay before retrying hasn't been reached, the program shouldn't be called
    # repeatedly on subsequent accesses.  But it should be called repeatedly if the delay has been
    # reached.
    settings = Settings()
    settings.database_source = "/path/to/program"
    with patch.object(Settings, "DB_URL_MIN_CACHE_TIME", new=15):
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.return_value = "sqlite:///cache.sqlite"
            assert settings.database_url == "sqlite:///cache.sqlite"
            assert settings.database_url == "sqlite:///cache.sqlite"
            assert mock_subprocess.call_count == 1
    settings = Settings()
    settings.database_source = "/path/to/program"
    with patch.object(Settings, "DB_URL_MAX_CACHE_TIME", new=0):
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.return_value = "sqlite:///cache.sqlite"
            assert settings.database_url == "sqlite:///cache.sqlite"
            assert settings.database_url == "sqlite:///cache.sqlite"
            assert mock_subprocess.call_count == 2
