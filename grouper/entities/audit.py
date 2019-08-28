from datetime import datetime
from enum import Enum, unique
from typing import List, NamedTuple


@unique
class MembershipAuditStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REMOVE = "remove"


# Contains audit information about members of a group
AuditMemberInfo = NamedTuple(
    "AuditMemberInfo",
    [
        # The ID of the audit for this one specific membership, not to be confused with the ID of
        # the global audit
        ("membership_audit_id", int),
        ("membership_audit_status", str),
        ("membership_role", str),  # e.g., "member", "manager", [np-]owner
        ("member_name", str),
        ("member_type", str),  # "User" or "Group"
    ],
)

GroupAuditInfo = NamedTuple(
    "GroupAuditInfo",
    [("id", int), ("complete", bool), ("started_at", datetime), ("ends_at", datetime)],
)

GroupAuditDetails = NamedTuple(
    "GroupAuditDetails",
    [
        ("id", int),
        ("complete", bool),
        ("started_at", datetime),
        ("ends_at", datetime),
        ("audit_members_infos", List[AuditMemberInfo]),
    ],
)
