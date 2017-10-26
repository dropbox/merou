from collections import namedtuple

from grouper.constants import USER_ADMIN
from grouper.models.audit_log import AuditLog
from grouper.models.base.session import Session  # noqa
from grouper.models.group import Group
from grouper.models.user import User
from grouper.user import disable_user, enable_user
from grouper.user_group import user_can_manage_group
from grouper.user_permissions import user_has_permission


class ServiceAccountNotFound(Exception):
    pass


ServiceAccount = namedtuple("ServiceAccount", ["user", "group"])


def create_service_account(session, actor, name, description, canjoin):
    # type (Session, User, str, str, str) -> None
    """Creates a service account with the given name, description, and canjoin status

    Args:
        session: the database session
        actor: the user creating the service account
        name: the name of the service account
        description: description of the service account
        canjoin: the canjoin status for management of the service account

    Throws:
        IntegrityError: if a user or group with the given name already exists
    """
    user = User(username=name, role_user=True)
    group = Group(groupname=name, description=description, canjoin=canjoin)

    user.add(session)
    group.add(session)

    group.add_member(actor, actor, "Group Creator", "actioned", None, "np-owner")
    group.add_member(actor, user, "Service Account", "actioned", None, "member")
    session.commit()

    AuditLog.log(session, actor.id, 'create_service_account', 'Created new service account.',
                 on_group_id=group.id, on_user_id=user.id)


def is_service_account(session, user=None, group=None):
    # type: (Session, User, Group) -> bool
    """
    Takes in a User or a Group and returns a boolean indicating whether
    that User/Group is a component of a service account.

    Args:
        session: the database session
        user: a User object to check
        group: a Group object to check

    Throws:
        AssertionError if neither a user nor a group is provided

    Returns:
        whether the User/Group is a component of a service account
    """
    assert user is not None or group is not None

    if user is not None:
        return user.role_user

    user = User.get(session, name=group.groupname)
    if not user:
        return False

    return user.role_user


def get_service_account(session, user=None, group=None):
    # type: (Session, User, Group) -> ServiceAccount
    """
    Takes in a User or a Group and returns a dictionary that contains
    all of the service account components for the service account that
    the user/group is part of.

    Args:
        session: the database session
        user: a User object to check
        group: a Group object to check

    Throws:
        ServiceAccountNotFound: if the user or group is not part of a
            service account

    Returns:
        a dictionary with all components of the service account of the
            user or group passed in
    """
    if not is_service_account(session, user, group):
        raise ServiceAccountNotFound()

    name = user.name if user else group.name
    return ServiceAccount(User.get(session, name=name), Group.get(session, name=name))


def can_manage_service_account(session, user, tuser=None, tgroup=None):
    # type: (Session, User, User, Group) -> bool
    """
    Indicates whether the user has permission to manage the service account
    that tuser/tgroup is part of

    Args:
        session: the database session
        user: the User whose permissions are being verified
        tuser: the service account User we're checking to see can be managed
        tgroup: the service account Group we're checking to see can be managed

    Returns:
        a boolean indicating if user can manage the service account of tuser/tgroup
    """
    try:
        target = get_service_account(session, tuser, tgroup)
    except ServiceAccountNotFound:
        return False

    if target.user.name == user.name:
        return True

    if user_can_manage_group(session, target.group, user):
        return True

    return user_has_permission(session, user, USER_ADMIN)


def is_owner_of_service_account(session, user, tuser=None, tgroup=None):
    # type: (Session, User, User, Group) -> bool
    """
    Indicates whether the user is an owner of the service account
    that tuser/tgroup is part of

    Args:
        session: the database session
        user: the User whose permissions are being verified
        tuser: the service account User we're checking to see is owned
        tgroup: the service account Group we're checking to see is owned

    Returns:
        a boolean indicating if user is an owner of the service account of tuser/tgroup
    """
    try:
        target = get_service_account(session, tuser, tgroup)
    except ServiceAccountNotFound:
        return False

    if target.user.name == user.name:
        return True

    if user.name in target.group.my_owners_as_strings():
        return True

    return user_has_permission(session, user, USER_ADMIN)


def disable_service_account(session, user=None, group=None):
    # type: (Session, User, Group) -> None
    """
    Disables all components of the service account corresponding to user/group.

    Args:
        session: the database session
        user: the User component of the service account to be disabled
        group: the Group component of the service account to be disabled
    """
    acc = get_service_account(session, user, group)

    disable_user(session, acc.user)
    acc.group.enabled = False
    acc.user.add(session)
    acc.group.add(session)


def enable_service_account(session, actor, preserve_membership, user=None, group=None):
    # type: (Session, User, bool, User, Group) -> None
    """
    Enabled all components of the service account corresponding to user/group.

    Args:
        session: the database session
        actor: the User that is enabling the service account
        preserve_membership: whether to preserve what groups the service account is in
        user: the User component of the service account to be enabled
        group: the Group component of the service account to be enabled
    """
    acc = get_service_account(session, user, group)

    enable_user(session, acc.user, actor, preserve_membership)
    acc.group.enabled = True
    acc.user.add(session)
    acc.group.add(session)
