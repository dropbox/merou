from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


class CtlCommand(object):
    """Implements a subcommand of grouper-ctl that needs a session and a graph."""

    __metaclass__ = ABCMeta

    @staticmethod
    @abstractmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
        """Add the arguments for this command to the provided parser."""
        pass

    @abstractmethod
    def run(self, args):
        # type: (Namespace) -> None
        """Run a command and return the exit status."""
        pass
