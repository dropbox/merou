from typing import TYPE_CHECKING

from grouper.settings import Settings

if TYPE_CHECKING:
    from typing import Optional


class ApiSettings(Settings):
    """Grouper API server settings."""

    def __init__(self):
        """Set up API defaults."""
        super(ApiSettings, self).__init__()

        # Keep attributes here in the same order as in config/dev.yaml.
        self.address = "127.0.0.1"
        self.debug = False
        self.num_processes = 1
        self.port = 8990
        self.refresh_interval = 60

    def update_from_config(self, filename=None, section="api"):
        # type: (Optional[str], Optional[str]) -> None
        super(ApiSettings, self).update_from_config(filename, section)
