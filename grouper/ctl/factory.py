from typing import TYPE_CHECKING

from grouper.ctl.permission import PermissionCommand
from grouper.graph import Graph
from grouper.models.base.session import get_db_engine, Session
from grouper.repositories.factory import RepositoryFactory
from grouper.services.factory import ServiceFactory
from grouper.settings import settings
from grouper.usecases.factory import UseCaseFactory
from grouper.util import get_database_url

if TYPE_CHECKING:
    from argparse import _SubParsersAction
    from grouper.ctl.base import CtlCommand
    from grouper.graph import GroupGraph
    from typing import Optional


class UnknownCommand(Exception):
    """Attempted to run a command with no known class."""

    pass


class CtlCommandFactory(object):
    """Construct and add parsers for grouper-ctl commands.

    Some grouper-ctl commands do not want a Session or GroupGraph (and in some cases cannot have a
    meaningful Session before they run, such as the command to set up the database).  The property
    methods in this factory lazily create those objects on demand so that the code doesn't run when
    those commands are instantiated.
    """

    def __init__(self, session=None, graph=None):
        # type: (Session, GroupGraph) -> None
        self._session = session
        self._graph = graph
        self._usecase_factory = None  # type: Optional[UseCaseFactory]

    @property
    def graph(self):
        # type: () -> GroupGraph
        if not self._graph:
            self._graph = Graph()
        return self._graph

    @property
    def session(self):
        # type: () -> Session
        if not self._session:
            db_engine = get_db_engine(get_database_url(settings))
            Session.configure(bind=db_engine)
            self._session = Session()
        return self._session

    @property
    def usecase_factory(self):
        # type: () -> UseCaseFactory
        if not self._usecase_factory:
            repository_factory = RepositoryFactory(self.session, self.graph)
            service_factory = ServiceFactory(repository_factory)
            self._usecase_factory = UseCaseFactory(service_factory)
        return self._usecase_factory

    def add_all_parsers(self, subparsers):
        # type: (_SubParsersAction) -> None
        parser = subparsers.add_parser("permission", help="Manipulate permissions")
        PermissionCommand.add_arguments(parser)

    def construct_command(self, command):
        # type: (str) -> CtlCommand
        if command == "permission":
            return self.construct_permission_command()
        else:
            raise UnknownCommand("unknown command {}".format(command))

    def construct_permission_command(self):
        # type: () -> PermissionCommand
        return PermissionCommand(self.usecase_factory)
