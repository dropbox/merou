from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import _SubParsersAction, Namespace
    from grouper.models.base.session import Session


class CtlCommand(object):
    """Implements a subcommand of grouper-ctl."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def add_parser(self, subparsers):
        # type: (_SubParsersAction) -> None
        """Add the parser for this subcommand."""
        pass

    @abstractmethod
    def run(self, args):
        # type: (Namespace) -> None
        """Run a command and return the exit status."""
        pass

    def set_session(self, session):
        # type: (Session) -> None
        """Set the database session for the command."""
        self.session = session
