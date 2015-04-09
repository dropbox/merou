from constants import PERMISSION_AUDITOR
from graph import Graph


class UserNotAuditor(Exception):
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


def can_join(group, user_or_group, role="member"):
    """Enforce audit rules on joining a group

    This applies the auditing rules to determine whether or not a given user can join the given
    group with the given role.

    Args:
        group (models.Group): The group to test against.
        user (models.User): The user attempting to join.
        role (str): The role being tested.

    Returns:
        bool: True if the user should be allowed per policy, False if not.
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
            "User {} lacks auditing permission, so may only have the member role.".format(
                user_or_group.name))

    # No, this is a group-joining-group case. In this situation we must walk the entire group
    # subtree and ensure that all owners/managers are considered auditors. This data is contained
    # in the group metadetails, which contains all eventual members.
    #
    # We have to fetch each group's details individually though to figure out what someone's role
    # is in that particular group.
    checked, queue = set(), [user_or_group.name]
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
                        "User {} is a {} of the {} group, but is not an auditor.".format(
                            chk_user, info["rolename"], cur_group))
        # Now put subgroups into the queue to examine.
        for chk_group, info in details["subgroups"].iteritems():
            if info["distance"] == 1:
                queue.append(chk_group)

    # No case failed, so we allow this action.
    return True
