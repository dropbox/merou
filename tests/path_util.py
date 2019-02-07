import os

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py.path import LocalPath  # noqa: F401
    from typing import Dict  # noqa: F401


# TODO(cbguder): Replace uses of this function with something that doesn't depend on code layout
def src_path(*args):
    # type: (*str) -> str
    root = os.path.join(__file__, "..", "..")
    path = os.path.join(root, *args)
    return os.path.normpath(path)


def db_url(tmpdir):
    # type: (LocalPath) -> str
    db_path = tmpdir.join("grouper.sqlite")
    return "sqlite:///{}".format(db_path)


def bin_env():
    # type: () -> Dict[str, str]
    """Return an environment suitable for running programs from bin."""
    return {
        "GROUPER_SETTINGS": src_path("config", "dev.yaml"),
        "PATH": os.environ["PATH"],
        "PYTHONPATH": src_path(),
    }
