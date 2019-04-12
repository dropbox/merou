from typing import cast, TYPE_CHECKING

from grouper.settings import Settings, settings as global_settings

if TYPE_CHECKING:
    from typing import Dict, List, Optional


class FrontendSettings(Settings):
    """Grouper frontend settings."""

    def __init__(self):
        """Set up frontend defaults."""
        super(FrontendSettings, self).__init__()

        # Keep attributes here in the same order as in config/dev.yaml.
        self.address = "127.0.0.1"
        self.port = 8989
        self.cdnjs_prefix = "//cdnjs.cloudflare.com"
        self.debug = False
        self.how_to_get_help = "if this is prod, ask someone to fix the how_to_get_help setting"
        self.num_processes = 1
        self.permission_request_dropdown_help = ""
        self.permission_request_text_help = ""
        self.refresh_interval = 60
        self.shell = (
            [["/bin/false", "Shell support in Grouper has not been setup by the administrator"]],
        )
        self.site_docs = []  # type: List[Dict[str, str]]
        self.user_auth_header = "X-Grouper-User"

    def update_from_config(self, filename=None, section="fe"):
        # type: (Optional[str], Optional[str]) -> None
        super(FrontendSettings, self).update_from_config(filename, section)


# See grouper.settings for more information about why this nonsense is here.
def settings():
    # type: () -> FrontendSettings
    """Return a global FrontendSettings for frontend code."""
    return cast(FrontendSettings, global_settings())
