from enum import Enum
from typing import List, NamedTuple, Optional

from grouper.constants import NAME_VALIDATION
from grouper.entities.audit import GroupAuditDetails
from grouper.entities.permission_grant import GroupPermissionGrantWithRevocability
from grouper.entities.permission_request import PermissionRequestWithApprovers


class GroupJoinPolicy(Enum):
    CAN_JOIN = "canjoin"
    CAN_ASK = "canask"
    NOBODY = "nobody"


Group = NamedTuple(
    "Group",
    [
        ("name", str),
        ("id", int),
        ("description", str),
        ("email_address", Optional[str]),
        ("join_policy", GroupJoinPolicy),
        ("enabled", bool),
        ("is_role_user", bool),
    ],
)

MemberInfo = NamedTuple(
    "MemberInfo",
    [
        ("name", str),
        ("type", str),
        ("membership_id", int),
        ("membership_role", str),
        ("membership_expiration", str),
        ("role_user", bool),
        ("is_service_account", bool),
    ],
)

GroupDetails = NamedTuple(
    "GroupDetails",
    [
        ("name", str),
        ("id", int),
        ("description", str),
        ("email_address", Optional[str]),
        ("join_policy", GroupJoinPolicy),
        ("enabled", bool),
        ("is_role_user", bool),
        ("members_infos", List[MemberInfo]),
        ("parent_groups", List[str]),
        ("service_account_names", List[str]),
        ("num_pending_join_requests", int),
        ("num_pending_join_requests_from_viewer", int),
        ("permission_grants", List[GroupPermissionGrantWithRevocability]),
        ("pending_permission_requests", List[PermissionRequestWithApprovers]),
        ("is_audited", bool),  # whether this is an audited group
        ("has_pending_audit", bool),  # whether there is an audit to be completed
        ("pending_audit_details", Optional[GroupAuditDetails]),
    ],
)

# The actions a user can perform on a group.
GroupAccess = NamedTuple(
    "GroupAccess",
    [
        ("can_change_enabled_status", bool),
        ("can_approve_join_requests", bool),
        ("can_add_members", bool),
        # Can edit basic information about the group such as description
        ("can_edit_group", bool),
        # Whether the user can leave the group
        ("can_leave", bool),
        # Whether the user can manage the group's service accounts
        ("can_manage_service_accounts", bool),
        # The user can edit members of the group that have these roles. For example, a manager can
        # edit "member"s but not owners or other managers.  TODO: currently some additional logic
        # is in the template, such as to prevent a user from editing their own membership. Consider
        # putting all that logic into the usecase.
        ("editable_roles", List),
        # Whether the user can remove the group's direct permission grants
        ("can_revoke_permissions", bool),
        # Whether the user can request permissions for the group
        ("can_request_permissions", bool),
        # Whether the user can directly grant permissions to the group
        ("can_add_permissions", bool),
        # Whether the user can complete the group's audit
        ("can_complete_audit", bool),
    ],
)


class GroupNotFoundException(Exception):
    """Attempt to operate on a group not found in the storage layer."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "Group {} not found".format(name)
        super(GroupNotFoundException, self).__init__(msg)


class InvalidGroupNameException(Exception):
    """A group name does not match the validation regex."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "Group name {} does not match validation regex {}".format(name, NAME_VALIDATION)
        super(InvalidGroupNameException, self).__init__(msg)
