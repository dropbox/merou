from typing import TYPE_CHECKING

from mock import call, MagicMock

from grouper.constants import PERMISSION_CREATE
from grouper.services.audit_log import AuditLogService
from grouper.services.permission import PermissionService
from grouper.usecases.disable_permission import DisablePermission
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


def test_permission_disable(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    mock_ui = MagicMock()
    audit_log = AuditLogService(session)
    service = PermissionService(session, audit_log)
    usecase = DisablePermission(session, "gary@a.co", mock_ui, service)
    usecase.disable_permission("audited")
    assert mock_ui.mock_calls == [call.disabled_permission("audited")]


def test_permission_disable_denied(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    mock_ui = MagicMock()
    audit_log = AuditLogService(session)
    service = PermissionService(session, audit_log)
    usecase = DisablePermission(session, "zorkian@a.co", mock_ui, service)
    usecase.disable_permission("audited")
    assert mock_ui.mock_calls == [
        call.disable_permission_failed_because_permission_denied("audited")
    ]


def test_permission_disable_system(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    mock_ui = MagicMock()
    audit_log = AuditLogService(session)
    service = PermissionService(session, audit_log)
    usecase = DisablePermission(session, "gary@a.co", mock_ui, service)
    usecase.disable_permission(PERMISSION_CREATE)
    assert mock_ui.mock_calls == [
        call.disable_permission_failed_because_system_permission(PERMISSION_CREATE)
    ]


def test_permission_not_found(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    mock_ui = MagicMock()
    audit_log = AuditLogService(session)
    service = PermissionService(session, audit_log)
    usecase = DisablePermission(session, "gary@a.co", mock_ui, service)
    usecase.disable_permission("nonexistent")
    assert mock_ui.mock_calls == [call.disable_permission_failed_because_not_found("nonexistent")]
