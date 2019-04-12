from typing import TYPE_CHECKING

from grouper.ctl.main import main
from tests.path_util import src_path

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from tests.setup import SetupTest


def call_main(session, *args):
    # type: (Session, *str) -> None
    argv = ["grouper-ctl", "-c", src_path("config", "dev.yaml")] + list(args)
    main(sys_argv=argv, session=session)


def run_ctl(setup, *args):
    # type: (SetupTest, *str) -> None
    argv = ["grouper-ctl", "-c", src_path("config", "dev.yaml")] + list(args)
    main(sys_argv=argv, session=setup.session)
