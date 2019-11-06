from typing import TYPE_CHECKING

from grouper.settings import set_global_settings, Settings

if TYPE_CHECKING:
    from typing import List, Optional


class CtlSettings(Settings):
    """grouper-ctl settings."""

    @staticmethod
    def global_settings_from_config(filename=None, section="ctl"):
        # type: (Optional[str], Optional[str]) -> CtlSettings
        """Create and return a new global Settings singleton."""
        settings = CtlSettings()
        settings.update_from_config(filename, section)
        set_global_settings(settings)
        return settings

    def __init__(self):
        # type: () -> None
        super().__init__()

        # Keep attributes here in the same order as in config/dev.yaml.
        self.oneoff_dirs = []  # type: List[str]
        self.oneoff_module_paths = []  # type: List[str]

    def update_from_config(self, filename=None, section="ctl"):
        # type: (Optional[str], Optional[str]) -> None
        super().update_from_config(filename, section)
