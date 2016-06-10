from grouper.constants import USER_ADMIN
from grouper.group import user_can_manage_group
from grouper.model_soup import Group
from grouper.models.user import User
from grouper.user import disable_user, enable_user, user_has_permission


class ServiceAccountNotFound(Exception):
    pass


def is_service_account(session, user=None, group=None):

    if not user and not group:
        return False

    if user is not None:
        return user.role_user

    user = User.get(session, name=group.groupname)
    if not user:
        return False

    return user.role_user


def get_service_account(session, user=None, group=None):
    if not is_service_account(session, user, group):
        raise ServiceAccountNotFound()

    name = user.name if user else group.name
    return {
        "user": User.get(session, name=name),
        "group": Group.get(session, name=name),
    }


def can_manage_service_account(session, user, tuser=None, tgroup=None):
    try:
        target = get_service_account(session, tuser, tgroup)
    except ServiceAccountNotFound:
        return False

    if target["user"].name == user.name:
        return True

    if user_can_manage_group(session, target["group"], user):
        return True

    return user_has_permission(session, user, USER_ADMIN)


def is_owner_of_service_account(session, user, tuser=None, tgroup=None):
    try:
        target = get_service_account(session, tuser, tgroup)
    except ServiceAccountNotFound:
        return False

    if target["user"].name == user.name:
        return True

    if user.name in target["group"].my_owners_as_strings():
        return True

    return user_has_permission(session, user, USER_ADMIN)


def disable_service_account(session, user=None, group=None):
    acc = get_service_account(session, user, group)

    disable_user(session, acc["user"])
    acc["group"].enabled = False
    acc["user"].add(session)
    acc["group"].add(session)


def enable_service_account(session, actor, preserve_membership, user=None, group=None):
    acc = get_service_account(session, user, group)

    enable_user(session, acc["user"], actor, preserve_membership)
    acc["group"].enabled = True
    acc["user"].add(session)
    acc["group"].add(session)
