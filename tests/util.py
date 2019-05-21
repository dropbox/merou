from typing import TYPE_CHECKING

import grouper.permissions

if TYPE_CHECKING:
    from datetime import datetime
    from grouper.graph import GroupGraph
    from grouper.models.group import Group
    from grouper.models.permission import Permission
    from grouper.models.request import Request
    from grouper.models.user import User
    from typing import Optional, Set, Union


def add_member(parent, member, role="member", expiration=None):
    # type: (Group, Union[User, Group], str, Optional[datetime]) -> Request
    return parent.add_member(
        member, member, "Unit Testing", "actioned", role=role, expiration=expiration
    )


def edit_member(parent, member, role="member", expiration=None):
    # type: (Group, Union[User, Group], str, Optional[datetime]) -> None
    parent.edit_member(member, member, "Unit Testing", role=role, expiration=expiration)


def revoke_member(parent, member):
    # type: (Group, Union[User, Group]) -> None
    parent.revoke_member(member, member, "Unit Testing")


def grant_permission(group, permission, argument=""):
    # type: (Group, Permission, str) -> None
    grouper.permissions.grant_permission(group.session, group.id, permission.id, argument=argument)


def get_users(graph, groupname, cutoff=None):
    # type: (GroupGraph, str, Optional[int]) -> Set[str]
    if cutoff:
        users = graph.get_group_details(groupname)["users"]
        result = set()
        for user in users:
            if users[user]["distance"] <= cutoff:
                result.add(user)
        return result
    else:
        return set(graph.get_group_details(groupname)["users"])


def get_groups(graph, username, cutoff=None):
    # type: (GroupGraph, str, Optional[int]) -> Set[str]
    if cutoff:
        groups = graph.get_user_details(username)["groups"]
        result = set()
        for group in groups:
            if groups[group]["distance"] <= cutoff:
                result.add(group)
        return result
    else:
        return set(graph.get_user_details(username)["groups"])


def get_user_permissions(graph, username, cutoff=None):
    # type: (GroupGraph, str, Optional[int]) -> Set[str]
    return {
        "{}:{}".format(permission["permission"], permission["argument"])
        for permission in graph.get_user_details(username)["permissions"]
        if not cutoff or permission["distance"] <= cutoff
    }


def get_group_permissions(graph, groupname, cutoff=None):
    # type: (GroupGraph, str, Optional[int]) -> Set[str]
    return {
        "{}:{}".format(permission["permission"], permission["argument"])
        for permission in graph.get_group_details(groupname)["permissions"]
        if not cutoff or permission["distance"] <= cutoff
    }
