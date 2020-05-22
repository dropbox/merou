from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import List, TYPE_CHECKING, Union

from grouper.constants import PERMISSION_AUDITOR
from grouper.graph import Graph, NoSuchGroup
from grouper.models.audit import Audit
from grouper.models.audit_member import AuditMember
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.user import User
from grouper.util import get_auditors_group_name

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.settings import Settings
    from sqlalchemy.orm.query import Query
    from typing import Set


class UserNotAuditor(Exception):
    pass


class GroupDoesNotHaveAuditPermission(Exception):
    pass


@dataclass(frozen=True)
class AuditMemberInfo:
    """Information about one member of an audit.

    Contains audit information about members of a group, mostly to avoid latencies of individual
    queries due to lazy loading when looking up fields of group members.

    Attributes:
        audit_member_obj: AuditMember model to allow updating of the audit status
        audit_member_role: Role as an int to avoid a lazy lookup of AuditMember.edge
        member_obj: Either a User or a Group corresponding to the audited member
    """

    audit_member_obj: AuditMember
    audit_member_role: int
    member_obj: Union[User, Group]


def user_is_auditor(username: str) -> bool:
    """Check if a user is an auditor, defined as having the audit permission."""
    graph = Graph()
    user_md = graph.get_user_details(username)
    for perm in user_md["permissions"]:
        if perm["permission"] == PERMISSION_AUDITOR:
            return True
    return False


def assert_controllers_are_auditors(group: Group) -> None:
    """Return whether not all owners/np-owners/managers in a group (and below) are auditors

    This is used to ensure that all of the people who can control a group (owners, np-owners,
    managers) and all subgroups (all the way down the tree) have audit permissions.

    Raises:
        UserNotAuditor: If a user is found that violates the audit training policy
    """
    graph = Graph()
    checked: Set[str] = set()
    queue = [group.name]
    while queue:
        cur_group = queue.pop()
        if cur_group in checked:
            continue
        checked.add(cur_group)
        details = graph.get_group_details(cur_group)
        for chk_user, info in details["users"].items():
            if chk_user in checked:
                continue
            # Only examine direct members of this group, because then the role is accurate.
            if info["distance"] == 1:
                if info["rolename"] == "member":
                    continue
                if user_is_auditor(chk_user):
                    checked.add(chk_user)
                else:
                    raise UserNotAuditor(
                        "User {} has role '{}' in the group {} but lacks the auditing "
                        "permission ('{}').".format(
                            chk_user, info["rolename"], cur_group, PERMISSION_AUDITOR
                        )
                    )
        # Now put subgroups into the queue to examine.
        for chk_group, info in details["subgroups"].items():
            if info["distance"] == 1:
                queue.append(chk_group)


def assert_can_join(group: Group, user_or_group: Union[Group, User], role: str = "member") -> None:
    """Enforce audit rules on joining a group

    This applies the auditing rules to determine whether or not a given user can join the given
    group with the given role.

    Args:
        group: The group to test against.
        user: The user attempting to join.
        role: The role being tested.

    Raises:
        UserNotAuditor: If a user is found that violates the audit training policy
    """
    # By definition, any user can join as a member to any group.
    if user_or_group.type == "User" and role == "member":
        return

    # Else, we have to check if the group is audited. If not, anybody can join.
    graph = Graph()
    group_md = graph.get_group_details(group.name)
    if not group_md["audited"]:
        return

    # Audited group. Easy case, let's see if we're checking a user. If so, the user must be
    # considered an auditor.
    if user_or_group.type == "User":
        if user_is_auditor(user_or_group.name):
            return
        raise UserNotAuditor(
            "User {} lacks the auditing permission ('{}') so may only have the "
            "'member' role in this audited group.".format(user_or_group.name, PERMISSION_AUDITOR)
        )

    # No, this is a group-joining-group case. In this situation we must walk the entire group
    # subtree and ensure that all owners/np-owners/managers are considered auditors. This data
    # is contained in the group metadetails, which contains all eventual members.
    #
    # We have to fetch each group's details individually though to figure out what someone's role
    # is in that particular group.
    assert_controllers_are_auditors(user_or_group)


def get_audits(session: Session, only_open: bool) -> Query:
    """Return audits in the system.

    Args:
        session: Database session
        only_open: Whether to filter by open audits
    """
    query = session.query(Audit).order_by(Audit.started_at)
    if only_open:
        query = query.filter(Audit.complete == False)
    return query


def get_auditors_group(settings: Settings, session: Session) -> Group:
    """Retrieve the group for auditors

    Return:
        Group object for the group for Grouper auditors, whose name is specified with the
        auditors_group setting.

    Raise:
        NoSuchGroup: Either the name for the auditors group is not configured, or
            the group does not exist in the database
        GroupDoesNotHaveAuditPermission: Group does not actually have the PERMISSION_AUDITOR
            permission
    """
    # TODO(rra): Use a different exception to avoid a dependency on grouper.graph
    group_name = get_auditors_group_name(settings)
    if not group_name:
        raise NoSuchGroup("Please ask your admin to configure the `auditors_group` settings")
    group = Group.get(session, name=group_name)
    if not group:
        raise NoSuchGroup("Please ask your admin to configure the default group for auditors")
    if not any([p.name == PERMISSION_AUDITOR for p in group.my_permissions()]):
        raise GroupDoesNotHaveAuditPermission()
    return group


def get_group_audit_members_infos(session: Session, group: Group) -> List[AuditMemberInfo]:
    """Get audit information about the members of a group.

    Note that only current members of the group are relevant, i.e., members of the group at the
    time the current audit was started but are no longer part of the group are excluded, as are
    members of the group added after the audit was started.
    """
    members_edge_ids = {member.edge_id for member in group.my_members().values()}
    user_members = (
        session.query(AuditMember, GroupEdge._role, User)
        .filter(
            AuditMember.audit_id == group.audit_id,
            AuditMember.edge_id == GroupEdge.id,
            GroupEdge.member_type == OBJ_TYPES["User"],
            GroupEdge.member_pk == User.id,
            # only those members who have not left the group after the audit started
            AuditMember.edge_id.in_(members_edge_ids),
        )
        .all()
    )

    group_members = (
        session.query(AuditMember, GroupEdge._role, Group)
        .filter(
            AuditMember.audit_id == group.audit_id,
            AuditMember.edge_id == GroupEdge.id,
            GroupEdge.member_type == OBJ_TYPES["Group"],
            GroupEdge.member_pk == Group.id,
            # only those members who have not left the group after the audit started
            AuditMember.edge_id.in_(members_edge_ids),
        )
        .all()
    )

    return [
        AuditMemberInfo(audit_member, audit_member_role, member_obj)
        for audit_member, audit_member_role, member_obj in itertools.chain(
            user_members, group_members
        )
    ]


def group_has_pending_audit_members(session: Session, group: Group) -> bool:
    """Check if a group still has memberships with "pending" audit status."""
    members_edge_ids = {member.edge_id for member in group.my_members().values()}
    audit_members_statuses = session.query(AuditMember.status).filter(
        AuditMember.audit_id == group.audit_id,
        AuditMember.status == "pending",
        # only those members who have not left the group after the audit started
        AuditMember.edge_id.in_(members_edge_ids),
    )
    return audit_members_statuses.count()
