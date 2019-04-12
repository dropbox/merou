from typing import cast, TYPE_CHECKING

from grouper.settings import Settings, settings as global_settings

if TYPE_CHECKING:
    from typing import List, Optional


class CtlSettings(Settings):
    """grouper-ctl settings."""

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
