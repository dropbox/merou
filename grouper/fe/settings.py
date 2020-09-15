from typing import cast, TYPE_CHECKING

from grouper.settings import set_global_settings, Settings, settings as global_settings

if TYPE_CHECKING:
    from typing import Dict, List, Optional


class FrontendSettings(Settings):
    """Grouper frontend settings."""

    @staticmethod
    def global_settings_from_config(filename=None, section="fe"):
        # type: (Optional[str], Optional[str]) -> FrontendSettings
        """Create and return a new global Settings singleton."""
        settings = FrontendSettings()
        settings.update_from_config(filename, section)
        set_global_settings(settings)
        return settings

    def __init__(self):
        """Set up frontend defaults."""
        super().__init__()

        # Keep attributes here in the same order as in config/dev.yaml.
        self.address = None  # type: Optional[str]
        self.port = 8989
        self.cdnjs_prefix = "https://cdnjs.cloudflare.com"
        self.debug = False
        self.how_to_get_help = "if this is prod, ask someone to fix the how_to_get_help setting"
        self.num_processes = 1
        self.permission_request_dropdown_help = ""
        self.permission_request_text_help = ""
        self.refresh_interval = 60
        self.shell = (
            [["/bin/false", "Shell support in Grouper has not been setup by the administrator"]],
        )
        self.metadata_options = {}  # type: Dict[List[str, str]]
        self.site_docs = []  # type: List[Dict[str, str]]

    def update_from_config(self, filename=None, section="fe"):
        # type: (Optional[str], Optional[str]) -> None
        super().update_from_config(filename, section)


# See grouper.settings for more information about why this nonsense is here.
def settings():
    # type: () -> FrontendSettings
    """Return a global FrontendSettings for frontend code."""
    return cast(FrontendSettings, global_settings())
