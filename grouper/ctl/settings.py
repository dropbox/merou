from typing import cast, TYPE_CHECKING

from grouper.settings import set_global_settings, Settings, settings as global_settings

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
        super(CtlSettings, self).__init__()

        # Keep attributes here in the same order as in config/dev.yaml.
        self.oneoff_dirs = []  # type: List[str]
        self.oneoff_module_paths = []  # type: List[str]

    def update_from_config(self, filename=None, section="ctl"):
        # type: (Optional[str], Optional[str]) -> None
        super(CtlSettings, self).update_from_config(filename, section)


# See grouper.settings for more information about why this nonsense is here.
def settings():
    # type: () -> CtlSettings
    """Return a global CtlSettings for grouper-ctl code."""
    return cast(CtlSettings, global_settings())
