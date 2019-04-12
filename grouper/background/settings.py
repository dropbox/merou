from typing import TYPE_CHECKING

from grouper.settings import Settings

if TYPE_CHECKING:
    from typing import Optional


class BackgroundSettings(Settings):
    """Grouper background processor settings."""

    def __init__(self):
        # type: () -> None
        super(BackgroundSettings, self).__init__()

        # Keep attributes here in the same order as in config/dev.yaml.
        self.sleep_interval = 60

    def update_from_config(self, filename=None, section="background"):
        # type: (Optional[str], Optional[str]) -> None
        super(BackgroundSettings, self).update_from_config(filename, section)
