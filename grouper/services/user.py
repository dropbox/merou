from typing import TYPE_CHECKING

from grouper.constants import (
    AUDIT_MANAGER,
    PERMISSION_ADMIN,
    PERMISSION_AUDITOR,
    PERMISSION_CREATE,
    PERMISSION_GRANT,
    USER_ADMIN,
)
from grouper.entities.group import GroupAccess
from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.entities.permission import PermissionAccess
from grouper.usecases.interfaces import UserInterface

if TYPE_CHECKING:
    from grouper.entities.permission_grant import GroupPermissionGrant
    from grouper.entities.user import User
    from grouper.repositories.group_edge import GroupEdgeRepository
    from grouper.repositories.interfaces import PermissionGrantRepository, PermissionRepository
    from grouper.repositories.user import UserRepository
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.interfaces import AuditLogInterface
    from typing import Dict, List


class UserService(UserInterface):
    """High-level logic to manipulate users."""

    def __init__(
        self,
        user_repository,  # type: UserRepository
        permission_repository,  # type: PermissionRepository
        permission_grant_repository,  # type: PermissionGrantRepository
        group_edge_repository,  # type: GroupEdgeRepository
        audit_log_service,  # type: AuditLogInterface
    ):
        # type: (...) -> None
        self.user_repository = user_repository
        self.permission_repository = permission_repository
        self.permission_grant_repository = permission_grant_repository
        self.group_edge_repository = group_edge_repository
        self.audit_log = audit_log_service

    def all_users(self):
        # type: () -> Dict[str, User]
        return self.user_repository.all_users()

    def disable_user(self, user, authorization):
        # type: (str, Authorization) -> None
        self.user_repository.disable_user(user)
        self.audit_log.log_disable_user(user, authorization)

    def groups_of_user(self, user):
        # type: (str) -> List[str]
        return self.group_edge_repository.groups_of_user(user)

    def direct_groups_of_user(self, user):
        # type: (str) -> List[str]
        return self.group_edge_repository.direct_groups_of_user(user)

    def permission_access_for_user(self, user, permission):
        # type: (str, str) -> PermissionAccess
        permission_admin = self.user_is_permission_admin(user)
        can_disable = permission_admin
        can_change_audited_status = permission_admin or self.user_is_audit_manager(user)
        return PermissionAccess(can_disable, can_change_audited_status)

    def is_group_owner(self, user, group):
        # type: (str, str) -> bool
        return self.group_edge_repository.user_is_owner_of_group(user, group)

    def group_access_for_user(self, user, group):
        # type: (str, str) -> GroupAccess
        user_is_owner = self.group_edge_repository.user_is_owner_of_group(user, group)
        user_is_approver = self.group_edge_repository.user_is_approver_of_group(user, group)
        user_is_in_group = (
            user_is_owner
            or user_is_approver
            or self.group_edge_repository.user_role_in_group(user, group) is not None
        )

        can_change_enabled_status = user_is_owner
        can_approve_join_requests = user_is_approver
        can_add_members = user_is_approver
        can_edit_group = user_is_approver
        can_leave = user_is_in_group and not user_is_owner
        can_manage_service_accounts = user_is_in_group
        can_revoke_permissions = user_is_owner
        can_request_permissions = user_is_in_group
        can_add_permissions = self.user_is_permission_admin(user)
        can_complete_audit = user_is_owner

        if user_is_owner:
            editable_roles = list(GROUP_EDGE_ROLES)
        elif user_is_approver:
            editable_roles = ["member"]
        else:
            editable_roles = []

        return GroupAccess(
            can_change_enabled_status=can_change_enabled_status,
            can_approve_join_requests=can_approve_join_requests,
            can_add_members=can_add_members,
            can_edit_group=can_edit_group,
            can_leave=can_leave,
            can_manage_service_accounts=can_manage_service_accounts,
            editable_roles=editable_roles,
            can_revoke_permissions=can_revoke_permissions,
            can_request_permissions=can_request_permissions,
            can_add_permissions=can_add_permissions,
            can_complete_audit=can_complete_audit,
        )

    def permission_grants_for_user(self, user):
        # type: (str) -> List[GroupPermissionGrant]
        return self.permission_grant_repository.permission_grants_for_user(user)

    def user_exists(self, user):
        # type: (str) -> bool
        return self.user_repository.user_exists(user)

    def user_is_audit_manager(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, AUDIT_MANAGER)

    def user_is_auditor(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_AUDITOR)

    def user_is_permission_admin(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_ADMIN)

    def user_is_user_admin(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, USER_ADMIN)

    def user_can_create_permissions(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_CREATE)

    def user_can_grant_some_permissions(self, user):
        # type: (str) -> bool
        return self.user_is_permission_admin(
            user
        ) or self.permission_grant_repository.user_has_permission(user, PERMISSION_GRANT)
