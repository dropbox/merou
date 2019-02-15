from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.graph import Graph
from grouper.models.base.session import get_db_engine, Session
from grouper.repositories.factory import RepositoryFactory
from grouper.services.factory import ServiceFactory
from grouper.settings import settings
from grouper.usecases.factory import UseCaseFactory
from grouper.util import get_database_url

if TYPE_CHECKING:
    from argparse import _SubParsersAction, Namespace
    from typing import Optional


class CtlCommand(object):
    """Implements a subcommand of grouper-ctl that needs a session and a graph."""

    __metaclass__ = ABCMeta

    @staticmethod
    @abstractmethod
    def add_parser(subparsers):
        # type: (_SubParsersAction) -> str
        """Add the parser for this subcommand and return the subcommand name."""
        pass

    def __init__(self, session):
        # type: (Optional[Session]) -> None
        if not session:
            db_engine = get_db_engine(get_database_url(settings))
            Session.configure(bind=db_engine)
            session = Session()
        repository_factory = RepositoryFactory(session, Graph())
        service_factory = ServiceFactory(session, repository_factory)
        self.usecase_factory = UseCaseFactory(service_factory)

    @abstractmethod
    def run(self, args):
        # type: (Namespace) -> None
        """Run a command and return the exit status."""
        pass
