from typing import TYPE_CHECKING

from grouper.ctl.main import main
from tests.fixtures import session  # noqa: F401

if TYPE_CHECKING:
    from grouper.models.base.session import Session


def call_main(session, *args):  # noqa: F811
    argv = ["grouper-ctl"] + list(args)
    return main(sys_argv=argv, start_config_thread=False, session=session)


class CtlTestRunner(object):
    """Runs a grouper-ctl command with a mocked session and database."""

    def __init__(self, session):  # noqa: F811
        # type: (Session) -> None
        self.session = session  # noqa: F811

    def run(self, *args):
        # type: (*str) -> None
        """Run grouper-ctl with a given set of arguments."""
        argv = ["grouper-ctl"] + list(args)
        main(sys_argv=argv, start_config_thread=False, session=self.session)
