"""
Base class for Grouper oneoffs. These are scripts are run in the grouper
environment via grouper-ctl.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class BaseOneOff:
    def configure(self, service_name):
        # type: (str) -> None
        """
        Called once the plugin is instantiated to identify the executable
        (grouper-api or grouper-fe).
        """
        pass

    def run(self, session, *args, **kwargs):
        # type: (str, *Any, **Any) -> None
        raise NotImplementedError
