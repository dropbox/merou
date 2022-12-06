import logging
import subprocess
from typing import TYPE_CHECKING

import pytest
import pytz
from mock import call, patch

from grouper.models.base.session import get_db_engine
from grouper.settings import DatabaseSourceException, InvalidSettingsError, Settings

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from pytest.logging import LogCaptureFixture

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
"""


def test_timezone():
    # type: () -> None
    settings = Settings()

    # mypy 0.700 thinks setting timezone to a str is a type mismatch because it doesn't understand
    # the type magic, so work around the type error by using setattr.
    setattr(settings, "timezone", "US/Eastern")
    assert settings.timezone == pytz.timezone("US/Eastern")


def test_update_from_config(tmpdir):
    # type: (LocalPath) -> None
    settings = Settings()

    # Create a config file that sets database to different values in different sections.
    config_path = str(tmpdir.join("test.yaml"))
    with open(config_path, "w") as config:
        config.write(CONFIG_SECTIONS)

    # Default loading should only see the common section, but another can be specified.
    settings.update_from_config(config_path)
    assert settings.database == "foo"
    settings.update_from_config(config_path, section="other")
    assert settings.database == "bar"

    # The timezone attribute is special and should be converted to a timezone on setting.
    assert settings.timezone == pytz.timezone("UTC")
    with open(config_path, "w") as config:
        config.write("common:\n  timezone: US/Pacific\n")
    settings.update_from_config(config_path)
    assert settings.timezone == pytz.timezone("US/Pacific")

    # Create a config file that tries to set unknown or internal attributes.
    with open(config_path, "w") as config:
        config.write(CONFIG_BOGUS)
    settings.update_from_config(config_path)
    assert settings._logger != "bar"  # type: ignore[comparison-overlap]
    assert not hasattr(settings, "foo")

    # A configuration that doesn't set database or database_source should raise an exception.
    settings = Settings()
    with open(config_path, "w") as config:
        config.write("common:\n  auditors_group: some-group\n")
    with pytest.raises(InvalidSettingsError):
        settings.update_from_config(config_path)


def test_database():
    # type: () -> None
    settings = Settings()

    # The default is uninitialized and should throw an error until we load a configuration.
    with pytest.raises(InvalidSettingsError):
        assert settings.database

    # If database is set, it should be used.
    settings.database = "sqlite:///grouper.sqlite"
    assert settings.database == "sqlite:///grouper.sqlite"
    settings.database_source = "/bin/false"
    assert settings.database == "sqlite:///grouper.sqlite"

    # If only database_source is set, it should be run to get a URL.
    settings.database = ""
    settings.database_source = "/path/to/program"
    with patch("subprocess.check_output") as mock_subprocess:
        mock_subprocess.return_value = b"sqlite:///other.sqlite\n"
        assert settings.database == "sqlite:///other.sqlite"
        assert mock_subprocess.call_args_list == [
            call(["/path/to/program"], stderr=subprocess.STDOUT)
        ]

    # If the command fails, it should be retried.  Disable the delay to not make the test slow.
    settings = Settings()
    settings.database_source = "/path/to/program"
    with patch.object(Settings, "DB_URL_RETRY_DELAY", new=0):
        with patch("subprocess.check_output") as mock_subprocess:
            exception = subprocess.CalledProcessError(1, "/path/to/program")
            mock_subprocess.side_effect = [exception, b"sqlite:///third.sqlite"]
            assert settings.database == "sqlite:///third.sqlite"
            assert mock_subprocess.call_count == 2

    # Commands that return an empty URL should also be retried.
    settings = Settings()
    settings.database_source = "/path/to/program"
    with patch.object(Settings, "DB_URL_RETRY_DELAY", new=0):
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.side_effect = [b"", b"sqlite:///notempty.sqlite"]
            assert settings.database == "sqlite:///notempty.sqlite"
            assert mock_subprocess.call_count == 2

    # Too many retries should raise an exception.
    settings = Settings()
    settings.database_source = "/path/to/program"
    with patch.object(Settings, "DB_URL_RETRY_DELAY", new=0):
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.return_value = b""
            with pytest.raises(DatabaseSourceException):
                assert settings.database


def test_mask_passsword_in_logs(caplog):
    # type: (LogCaptureFixture) -> None
    settings = Settings()
    settings._logger.setLevel(logging.DEBUG)
    settings.database_source = "/path/to/program"
    test_url = "mysql://user:password@example.com:8888/merou"

    # Reading settings.database will run the external program and trigger the logging.
    with patch("subprocess.check_output") as mock_subprocess:
        mock_subprocess.return_value = b"mysql://user:password@example.com:8888/merou"
        assert settings.database == test_url

    assert test_url not in caplog.text
    assert "REDACTED" in caplog.text


def test_bad_db_url():
    # type: () -> None
    bad_url = "This is not even a valid URL"
    with pytest.raises(InvalidSettingsError):
        engine = get_db_engine(bad_url)
        assert engine
