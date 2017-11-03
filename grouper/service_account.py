"""Service account handling.

A service account is an account that is not a Grouper user and cannot be a member of groups, but
can have permissions delegated to it.  Every service account is owned by one and only one Group.

In an ideal world, we would have an Account abstraction, and both a User and a ServiceAccount would
contain an Account.  The Account would hold the data in common betweeen User and ServiceAccount.
In practice, that would mean a huge database migration, so User does double duty as the underlying
Account abstraction.  A User that's just the account of a ServiceAccount is flagged with the
service_account boolean field.
"""

from typing import Union  # noqa

from grouper.group import add_service_account
from grouper.models.audit_log import AuditLog
from grouper.models.base.session import Session  # noqa
from grouper.models.counter import Counter
from grouper.models.group import Group  # noqa
from grouper.models.service_account import ServiceAccount
from grouper.models.service_account_permission_map import ServiceAccountPermissionMap
from grouper.models.user import User
from grouper.user import disable_user, enable_user


def create_service_account(session, actor, name, description, machine_set, owner):
    # type: (Session, User, str, str, str, Group) -> ServiceAccount
    """Creates a service account and its underlying user.

    Also adds the service account to the list of accounts managed by the owning group.

    Throws:
        IntegrityError: if a user with the given name already exists
    """
    user = User(username=name, is_service_account=True)
    service_account = ServiceAccount(user=user, description=description, machine_set=machine_set)

    user.add(session)
    service_account.add(session)
    session.flush()

    add_service_account(session, owner, service_account)

    AuditLog.log(session, actor.id, "create_service_account", "Created new service account.",
                 on_group_id=owner.id, on_user_id=service_account.user_pk)

    return service_account


def is_service_account(session, user):
    # type: (Session, User) -> bool
    """Returns whether a User is a service account.

    Also returns True for role users until they have been retired.
    """
    return user.is_service_account or user.role_user


def can_manage_service_account(session, target, user):
    # type: (Session, Union[ServiceAccount, User], User) -> bool
    """Returns whether a User has permission to manage a ServiceAccount."""
    if type(target) == User:
        if not target.is_service_account:
            return False
        account = target.service_account
    else:
        account = target
    if account.owner is None:
        return False
    return user.is_member(account.owner.group.my_members())


def disable_service_account(session, actor, service_account):
    # type: (Session, User, ServiceAccount) -> None
    """Disables a service account and deletes the association with a Group."""
    disable_user(session, service_account.user)
    owner_id = service_account.owner.group.id
    service_account.owner.delete(session)
    permissions = session.query(ServiceAccountPermissionMap).filter_by(
        service_account_id=service_account.id)
    for permission in permissions:
        permission.delete(session)

    AuditLog.log(session, actor.id, "disable_service_account", "Disabled service account.",
                 on_group_id=owner_id, on_user_id=service_account.user_pk)

    Counter.incr(session, "updates")
    session.commit()


def enable_service_account(session, actor, service_account, owner):
    # type: (Session, User, ServiceAccount, Group) -> None
    """Enables a service account and sets a new owner."""
    enable_user(session, service_account.user, actor, preserve_membership=False)
    add_service_account(session, owner, service_account)

    AuditLog.log(session, actor.id, "enable_service_account", "Enabled service account.",
                 on_group_id=owner.id, on_user_id=service_account.user_pk)

    Counter.incr(session, "updates")
    session.commit()
