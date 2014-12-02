
def add_member(parent, member, role="member"):
    return parent.add_member(member, member, "Unit Testing", "actioned", role=role)


def grant_permission(group, permission, argument=""):
    return group.grant_permission(permission, argument=argument)


def get_users(graph, groupname, cutoff=None):
    return set(graph.get_group_details(groupname, cutoff)["users"])


def get_groups(graph, username, cutoff=None):
    return set(graph.get_user_details(username, cutoff)["groups"])


def get_user_permissions(graph, username, cutoff=None):
    return {"{}:{}".format(permission["permission"], permission["argument"])
            for permission in graph.get_user_details(username, cutoff)["permissions"]}


def get_group_permissions(graph, groupname, cutoff=None):
    return {"{}:{}".format(permission["permission"], permission["argument"])
            for permission in graph.get_group_details(groupname, cutoff)["permissions"]}
