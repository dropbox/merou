from mock import patch
from typing import TYPE_CHECKING

from fixtures import session
from grouper.ctl.main import main

if TYPE_CHECKING:
    from grouper.models.base.session import Session


def call_main(session, *args):
    argv = ['grouper-ctl'] + list(args)
    return main(sys_argv=argv, start_config_thread=False, session=session)


class CtlTestRunner(object):
    """Runs a grouper-ctl command with a mocked session and database."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def run(self, *args):
        # type: (*str) -> None
        """Run grouper-ctl with a given set of arguments."""
        argv = ["grouper-ctl"] + list(args)
        main(sys_argv=argv, start_config_thread=False, session=self.session)
