from typing import TYPE_CHECKING

from mock import call, MagicMock

from grouper.constants import PERMISSION_CREATE
from grouper.repositories.factory import RepositoryFactory
from grouper.services.factory import ServiceFactory
from grouper.usecases.factory import UseCaseFactory
from tests.fixtures import (  # noqa: F401
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)

if TYPE_CHECKING:
    from dropbox.models.base.session import Session
    from dropbox.graph import GroupGraph
    from grouper.usecases.disable_permission import DisablePermission


def create_disable_permission_usecase(session, actor, ui):  # noqa: F811
    # type: (Session, str, MagicMock) -> DisablePermission
    repository_factory = RepositoryFactory(session)
    service_factory = ServiceFactory(session, repository_factory)
    usecase_factory = UseCaseFactory(service_factory)
    return usecase_factory.create_disable_permission_usecase(actor, ui)


def test_permission_disable(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    mock_ui = MagicMock()
    usecase = create_disable_permission_usecase(session, "gary@a.co", mock_ui)
    usecase.disable_permission("audited")
    assert mock_ui.mock_calls == [call.disabled_permission("audited")]


def test_permission_disable_denied(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    mock_ui = MagicMock()
    usecase = create_disable_permission_usecase(session, "zorkian@a.co", mock_ui)
    usecase.disable_permission("audited")
    assert mock_ui.mock_calls == [
        call.disable_permission_failed_because_permission_denied("audited")
    ]


def test_permission_disable_system(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    mock_ui = MagicMock()
    usecase = create_disable_permission_usecase(session, "gary@a.co", mock_ui)
    usecase.disable_permission(PERMISSION_CREATE)
    assert mock_ui.mock_calls == [
        call.disable_permission_failed_because_system_permission(PERMISSION_CREATE)
    ]


def test_permission_not_found(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    mock_ui = MagicMock()
    usecase = create_disable_permission_usecase(session, "gary@a.co", mock_ui)
    usecase.disable_permission("nonexistent")
    assert mock_ui.mock_calls == [call.disable_permission_failed_because_not_found("nonexistent")]
