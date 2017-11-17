from sqlalchemy.sql import label

from grouper.models.base.constants import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GROUP_EDGE_ROLES, OWNER_ROLE_INDICES, GroupEdge
from grouper.models.user import User
from grouper.plugin import BasePlugin, PluginException

EXCEPTION_MESSAGE = "You can't remove the last permanent owner of a group"


class GroupOwnershipPolicyViolation(PluginException):
    """This exception is raised when trying to remove the last owner of a group."""
    pass


def _validate_not_last_permanent_owner(session, group, member):
    perm_owners = session.query(
        label("name", User.username)
    ).filter(
        GroupEdge.group_id == group.id,
        GroupEdge.member_pk == User.id,
        GroupEdge.member_type == OBJ_TYPES["User"],
        GroupEdge._role.in_(OWNER_ROLE_INDICES),
        GroupEdge.active == True,
        User.enabled == True,
        GroupEdge.expiration == None
    )

    perm_owner_usernames = [user[0] for user in perm_owners]

    if perm_owner_usernames == [member.username]:
        raise GroupOwnershipPolicyViolation(EXCEPTION_MESSAGE)


def _get_permanently_owned_groups_by_user(session, user):
    return session.query(
        Group
    ).filter(
        GroupEdge.member_pk == user.id,
        GroupEdge.member_type == OBJ_TYPES["User"],
        GroupEdge._role.in_(OWNER_ROLE_INDICES),
        GroupEdge.active == True,
        Group.enabled == True,
        GroupEdge.expiration == None,
    )


class GroupOwnershipPolicyPlugin(BasePlugin):
    def will_update_group_membership(self, session, group, member, **updates):
        if member.member_type != OBJ_TYPES["User"]:
            return

        check_permanent_owners = False

        if "role" in updates:
            role_idx = GROUP_EDGE_ROLES.index(updates["role"])
            if role_idx not in OWNER_ROLE_INDICES:
                check_permanent_owners = True

        if "expiration" in updates:
            check_permanent_owners = True

        if "active" in updates and not updates["active"]:
            check_permanent_owners = True

        if check_permanent_owners:
            _validate_not_last_permanent_owner(session, group, member)

    def will_disable_user(self, session, user):
        groups = _get_permanently_owned_groups_by_user(session, user)

        for group in groups:
            _validate_not_last_permanent_owner(session, group, user)
