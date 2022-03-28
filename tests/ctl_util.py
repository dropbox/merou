from typing import TYPE_CHECKING

from grouper.ctl.main import main
from tests.path_util import db_url, src_path

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from py._path.local import LocalPath
    from tests.setup import SetupTest


def call_main(session, tmpdir, *args):
    # type: (Session, LocalPath, *str) -> None
    """Legacy test driver, use run_ctl instead for all new code."""
    config_path = src_path("config", "test.yaml")
    argv = ["grouper-ctl", "-c", config_path, "-d", db_url(tmpdir)] + list(args)
    main(sys_argv=argv, session=session)


def run_ctl(setup, *args):
    # type: (SetupTest, *str) -> None
    config_path = src_path("config", "test.yaml")
    argv = ["grouper-ctl", "-c", config_path, "-d", setup.settings.database] + list(args)
    main(sys_argv=argv, session=setup.session)
