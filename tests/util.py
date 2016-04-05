import grouper.permissions

# These functions operate on and return instrumented Grouper.models.Model instances.
def add_member(parent, member, role="member", expiration=None):
    return parent.add_member(member, member, "Unit Testing", "actioned", role=role,
                             expiration=expiration)

def edit_member(parent, member, role="member", expiration=None):
    return parent.edit_member(member, member, "Unit Testing", role=role,
                              expiration=expiration)

def revoke_member(parent, member):
    return parent.revoke_member(member, member, "Unit Testing")

def grant_permission(group, permission, argument=""):
    return grouper.permissions.grant_permission(group.session, group.id, permission.id,
            argument=argument)


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
