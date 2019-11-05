from typing import TYPE_CHECKING

from grouper.settings import set_global_settings, Settings

if TYPE_CHECKING:
    from typing import Optional


class ApiSettings(Settings):
    """Grouper API server settings."""

    @staticmethod
    def global_settings_from_config(filename=None, section="api"):
        # type: (Optional[str], Optional[str]) -> ApiSettings
        """Create and return a new global Settings singleton."""
        settings = ApiSettings()
        settings.update_from_config(filename, section)
        set_global_settings(settings)
        return settings

    def __init__(self):
        """Set up API defaults."""
        super().__init__()

        # Keep attributes here in the same order as in config/dev.yaml.
        self.address = None  # type: Optional[str]
        self.debug = False
        self.num_processes = 1
        self.port = 8990
        self.refresh_interval = 60

    def update_from_config(self, filename=None, section="api"):
        # type: (Optional[str], Optional[str]) -> None
        super().update_from_config(filename, section)
