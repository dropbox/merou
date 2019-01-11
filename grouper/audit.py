from grouper.constants import PERMISSION_AUDITOR
from grouper.graph import Graph, NoSuchGroup
from grouper.models.audit import Audit
from grouper.models.group import Group
from grouper.settings import settings
from grouper.util import get_auditors_group_name


class UserNotAuditor(Exception):
    pass


class GroupDoesNotHaveAuditPermission(Exception):
    pass


def user_is_auditor(username):
    """Check if a user is an auditor

    This is defined as the user having the audit permission.

    Args:
        username (str): The account name to check.

    Returns:
        bool: True/False.
    """
    graph = Graph()
    user_md = graph.get_user_details(username)
    for perm in user_md["permissions"]:
        if perm["permission"] == PERMISSION_AUDITOR:
            return True
    return False


def assert_controllers_are_auditors(group):
    """Return whether not all owners/np-owners/managers in a group (and below) are auditors

    This is used to ensure that all of the people who can control a group
    (owners, np-owners, managers) and all subgroups (all the way down the tree)
    have audit permissions.

    Raises:
        UserNotAuditor: If a user is found that violates the audit training policy, then this
            exception is raised.

    Returns:
        bool: True if the tree is completely controlled by auditors, else it will raise as above.
    """
    graph = Graph()
    checked, queue = set(), [group.name]
    while queue:
        cur_group = queue.pop()
        if cur_group in checked:
            continue
        details = graph.get_group_details(cur_group)
        for chk_user, info in details["users"].iteritems():
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
                            chk_user, info["rolename"], cur_group, PERMISSION_AUDITOR))
        # Now put subgroups into the queue to examine.
        for chk_group, info in details["subgroups"].iteritems():
            if info["distance"] == 1:
                queue.append(chk_group)

    # If we didn't raise, we're valid.
    return True


def assert_can_join(group, user_or_group, role="member"):
    """Enforce audit rules on joining a group

    This applies the auditing rules to determine whether or not a given user can join the given
    group with the given role.

    Args:
        group (models.Group): The group to test against.
        user (models.User): The user attempting to join.
        role (str): The role being tested.

    Raises:
        UserNotAuditor: If a user is found that violates the audit training policy, then this
            exception is raised.

    Returns:
        bool: True if the user should be allowed per policy, else it will raise as above.
    """
    # By definition, any user can join as a member to any group.
    if user_or_group.type == "User" and role == "member":
        return True

    # Else, we have to check if the group is audited. If not, anybody can join.
    graph = Graph()
    group_md = graph.get_group_details(group.name)
    if not group_md["audited"]:
        return True

    # Audited group. Easy case, let's see if we're checking a user. If so, the user must be
    # considered an auditor.
    if user_or_group.type == "User":
        if user_is_auditor(user_or_group.name):
            return True
        raise UserNotAuditor(
            "User {} lacks the auditing permission ('{}') so may only have the "
            "'member' role in this audited group.".format(
                user_or_group.name, PERMISSION_AUDITOR))

    # No, this is a group-joining-group case. In this situation we must walk the entire group
    # subtree and ensure that all owners/np-owners/managers are considered auditors. This data
    # is contained in the group metadetails, which contains all eventual members.
    #
    # We have to fetch each group's details individually though to figure out what someone's role
    # is in that particular group.
    return assert_controllers_are_auditors(user_or_group)


def get_audits(session, only_open):
    """Return audits in the system.

    Args:
        session (session): database session
        only_open (bool): whether to filter by open audits
    """
    query = session.query(Audit).order_by(Audit.started_at)

    if only_open:
        query = query.filter(Audit.complete == False)

    return query


def get_auditors_group(session):
    """Retrieve the group for auditors

    Arg(s):
        session (session): database session

    Return:
        Group object for the group for Grouper auditors, whose name is
        specified with `auditors_group` settings.

    Raise:
        Raise NoSuchGroup exception if either the name for the
        auditors group is not configured, or the group does not exist
        in the database. Raise GroupDoesNotHaveAuditPermission if the group
        does not actually have the PERMISSION_AUDITOR permission.
    """
    group_name = get_auditors_group_name(settings)
    if not group_name:
        raise NoSuchGroup('Please ask your admin to configure the default auditors group name')
    group = Group.get(session, name=group_name)
    if not group:
        raise NoSuchGroup('Please ask your admin to configure the default group for auditors')
    if not any([p.name == PERMISSION_AUDITOR for p in group.my_permissions()]):
        raise GroupDoesNotHaveAuditPermission()
    return group
