from typing import TYPE_CHECKING

from grouper.settings import set_global_settings, Settings

if TYPE_CHECKING:
    from typing import Optional


class BackgroundSettings(Settings):
    """Grouper background processor settings."""

    @staticmethod
    def global_settings_from_config(filename=None, section="background"):
        # type: (Optional[str], Optional[str]) -> BackgroundSettings
        """Create and return a new global Settings singleton."""
        settings = BackgroundSettings()
        settings.update_from_config(filename, section)
        set_global_settings(settings)
        return settings

    def __init__(self):
        # type: () -> None
        super().__init__()

        # Keep attributes here in the same order as in config/dev.yaml.
        self.sleep_interval = 60

    def update_from_config(self, filename=None, section="background"):
        # type: (Optional[str], Optional[str]) -> None
        super().update_from_config(filename, section)
