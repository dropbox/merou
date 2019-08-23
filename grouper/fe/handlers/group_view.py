from typing import TYPE_CHECKING

from grouper.entities.audit import MembershipAuditStatus
from grouper.entities.group import GroupDetails
from grouper.fe.util import Alert, GrouperHandler
from grouper.usecases.view_group import ViewGroupUI

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.group import GroupAccess
    from typing import Any, List


class GroupView(GrouperHandler, ViewGroupUI):
    def viewed_group(
        self,
        group_details,  # type: GroupDetails
        access,  # type: GroupAccess
        viewer_can_manage_some_permission_grants,  # type: bool
        audit_log_entries,  # type: List[AuditLogEntry]
    ):
        # type: (...) -> None
        alerts = []
        if group_details.num_pending_join_requests_from_viewer:
            alerts.append(Alert("info", "You have a pending request to join this group.", None))
        self.render(
            "group.html",
            group_details=group_details,
            pending_audit_details=group_details.pending_audit_details,
            audit_statuses=[e.value for e in MembershipAuditStatus],
            access=access,
            num_pending_join_requests=group_details.num_pending_join_requests,
            alerts=alerts,
            audit_log_entries=audit_log_entries,
            viewer_can_manage_some_permission_grants=viewer_can_manage_some_permission_grants,
            # temp hack, due to enabling StrictUndefined
            search_query="MY search!!!",
        )

    def view_group_failed_not_found(self, name):
        # type: (str) -> None
        self.notfound()

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        name = kwargs["name"]  # type: str
        usecase = self.usecase_factory.create_view_group_usecase(self)
        usecase.view_group(name, self.current_user.username, audit_log_limit=20)
