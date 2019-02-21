from typing import TYPE_CHECKING

from grouper.ctl.main import main

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from tests.setup import SetupTest


def call_main(session, *args):
    # type: (Session, *str) -> None
    argv = ["grouper-ctl"] + list(args)
    main(sys_argv=argv, start_config_thread=False, session=session)


def run_ctl(setup, *args):
    # type: (SetupTest, *str) -> None
    argv = ["grouper-ctl"] + list(args)
    main(sys_argv=argv, start_config_thread=False, session=setup.session, graph=setup.graph)
