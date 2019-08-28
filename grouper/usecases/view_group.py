from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from six import with_metaclass

from grouper.entities.group import GroupAccess, GroupDetails
from grouper.entities.permission_grant import (
    GrantablePermission,
    GroupPermissionGrantWithRevocability,
)
from grouper.entities.permission_request import PermissionRequestWithApprovers

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.usecases.interfaces import (
        AuditInterface,
        AuditLogInterface,
        GroupInterface,
        PermissionInterface,
        UserInterface,
    )
    from typing import List


class ViewGroupUI(with_metaclass(ABCMeta, object)):
    """Abstract base class for UI for ViewGroup."""

    @abstractmethod
    def viewed_group(
        self,
        group_details,  # type: GroupDetails
        access,  # type: GroupAccess
        viewer_can_manage_some_permission_grants,  # type: bool
        audit_log_entries,  # type: List[AuditLogEntry]
    ):
        # type: (...) -> None
        pass

    @abstractmethod
    def view_group_failed_not_found(self, name):
        # type: (str) -> None
        pass


class ViewGroup(object):
    """View a single group."""

    def __init__(
        self,
        ui,  # type: ViewGroupUI
        group_service,  # type: GroupInterface
        permission_service,  # type: PermissionInterface
        user_service,  # type: UserInterface
        audit_service,  # type: AuditInterface
        audit_log_service,  # type: AuditLogInterface
    ):
        # type: (...) -> None
        self.ui = ui
        self.group_service = group_service
        self.permission_service = permission_service
        self.user_service = user_service
        self.audit_service = audit_service
        self.audit_log_service = audit_log_service

    def view_group(self, name, actor, audit_log_limit):
        # type: (str, str, int) -> None
        group = self.group_service.group(name)
        if not group:
            self.ui.view_group_failed_not_found(name)
            return

        audit_log = self.audit_log_service.entries_affecting_group(name, audit_log_limit)
        access = self.user_service.group_access_for_user(actor, name)
        pending_join_requests = self.group_service.pending_join_requests(name)
        actor_is_owner_of_viewed_group = self.user_service.is_group_owner(actor, name)

        group_permission_grants = self.group_service.permission_grants(name)
        approver_groups_by_existing_grant = {
            gpg: set(
                self.permission_service.groups_that_can_approve_grant(
                    GrantablePermission(name=gpg.permission, argument=gpg.argument)
                )
            )
            for gpg in group_permission_grants
        }

        # Annotate each of the group's permission grants with revocability info. The user can
        # revoke only permission grants that are granted directly to the group, and only if the
        # user is either an owner of the group or is a controller of the permission grant.
        annotated_group_permission_grants = []
        direct_groups_of_actor = set(self.user_service.direct_groups_of_user(actor))
        for gpg in group_permission_grants:
            if gpg.group == name and (
                actor_is_owner_of_viewed_group
                or approver_groups_by_existing_grant[gpg].intersection(direct_groups_of_actor)
            ):
                actor_can_revoke = True
            else:
                actor_can_revoke = False
            annotated_gpg = GroupPermissionGrantWithRevocability(
                group=gpg.group,
                permission=gpg.permission,
                argument=gpg.argument,
                granted_on=gpg.granted_on,
                is_alias=gpg.is_alias,
                grant_id=gpg.grant_id,
                viewer_can_revoke=actor_can_revoke,
            )
            annotated_group_permission_grants.append(annotated_gpg)

        pending_permission_grant_requests = self.group_service.pending_permission_grant_requests(
            name
        )
        approver_groups_by_pending_grant = {
            gpg: self.permission_service.groups_that_can_approve_grant(
                GrantablePermission(name=gpg.grant.name, argument=gpg.grant.argument)
            )
            for gpg in pending_permission_grant_requests
        }
        annotated_pending_permission_grant_requests = []
        for ppgr in pending_permission_grant_requests:
            annotated_pending_permission_grant_requests.append(
                PermissionRequestWithApprovers(
                    group=ppgr.group,
                    grant=ppgr.grant,
                    status=ppgr.status,
                    approver_groups=approver_groups_by_pending_grant[ppgr],
                )
            )

        pending_audit_details = self.audit_service.group_pending_audit_details(name)

        group_details = GroupDetails(
            name=group.name,
            id=group.id,
            description=group.description,
            email_address=group.email_address,
            join_policy=group.join_policy,
            enabled=group.enabled,
            is_role_user=group.is_role_user,
            members_infos=self.group_service.members_infos(name),
            parent_groups=self.group_service.direct_parent_groups(name),
            num_pending_join_requests=len(pending_join_requests),
            num_pending_join_requests_from_viewer=len(
                [req for req in pending_join_requests if req.user == actor]
            ),
            pending_permission_requests=annotated_pending_permission_grant_requests,
            is_audited=self.audit_service.is_group_audited(name),
            has_pending_audit=bool(pending_audit_details),
            pending_audit_details=pending_audit_details,
            service_account_names=self.group_service.service_accounts(name),
            permission_grants=annotated_group_permission_grants,
        )
        self.ui.viewed_group(
            group_details,
            access,
            self.user_service.user_can_grant_some_permissions(actor),
            audit_log,
        )
