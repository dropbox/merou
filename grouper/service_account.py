"""Service account handling.

A service account is an account that is not a Grouper user and cannot be a member of groups, but
can have permissions delegated to it.  Every service account is owned by one and only one Group.

In an ideal world, we would have an Account abstraction, and both a User and a ServiceAccount would
contain an Account.  The Account would hold the data in common betweeen User and ServiceAccount.
In practice, that would mean a huge database migration, so User does double duty as the underlying
Account abstraction.  A User that's just the account of a ServiceAccount is flagged with the
service_account boolean field.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from grouper.entities.permission_grant import ServiceAccountPermissionGrant
from grouper.group_service_account import add_service_account
from grouper.models.audit_log import AuditLog
from grouper.models.counter import Counter
from grouper.models.permission import Permission
from grouper.models.service_account import ServiceAccount
from grouper.models.service_account_permission_map import ServiceAccountPermissionMap
from grouper.models.user import User
from grouper.plugin import get_plugin_proxy
from grouper.plugin.exceptions import PluginRejectedMachineSet
from grouper.user import disable_user, enable_user
from grouper.user_permissions import user_is_user_admin

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.group import Group
    from typing import Dict, List, Union


class BadMachineSet(Exception):
    """The service account machine set was rejected."""

    pass


def _check_machine_set(service_account, machine_set):
    # type: (ServiceAccount, str) -> None
    """Verify a service account machine set with plugins.

    Raises:
        BadMachineSet: if some plugin rejected the machine set
    """
    try:
        get_plugin_proxy().check_machine_set(service_account.user.username, machine_set)
    except PluginRejectedMachineSet as e:
        raise BadMachineSet(str(e))


def edit_service_account(session, actor, service_account, description, machine_set):
    # type: (Session, User, ServiceAccount, str, str) -> None
    """Update the description and machine set of a service account.

    Raises:
        PluginRejectedMachineSet: if some plugin rejected the machine set
    """
    if machine_set is not None:
        _check_machine_set(service_account, machine_set)

    service_account.description = description
    service_account.machine_set = machine_set
    Counter.incr(session, "updates")

    session.commit()

    AuditLog.log(
        session,
        actor.id,
        "edit_service_account",
        "Edited service account.",
        on_user_id=service_account.user.id,
    )


def can_manage_service_account(session, target, user):
    # type: (Session, Union[ServiceAccount, User], User) -> bool
    """Returns whether a User has permission to manage a ServiceAccount."""
    if user_is_user_admin(session, user):
        return True
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
        service_account_id=service_account.id
    )
    for permission in permissions:
        permission.delete(session)

    AuditLog.log(
        session,
        actor.id,
        "disable_service_account",
        "Disabled service account.",
        on_group_id=owner_id,
        on_user_id=service_account.user_id,
    )

    Counter.incr(session, "updates")
    session.commit()


def enable_service_account(session, actor, service_account, owner):
    # type: (Session, User, ServiceAccount, Group) -> None
    """Enables a service account and sets a new owner."""
    enable_user(session, service_account.user, actor, preserve_membership=False)
    add_service_account(session, owner, service_account)

    AuditLog.log(
        session,
        actor.id,
        "enable_service_account",
        "Enabled service account.",
        on_group_id=owner.id,
        on_user_id=service_account.user_id,
    )

    Counter.incr(session, "updates")
    session.commit()


def service_account_permissions(session, service_account):
    # type: (Session, ServiceAccount) -> List[ServiceAccountPermissionGrant]
    """Return the permissions of a service account, including mapping IDs.

    This is used to display the permission grants on a service account page, which has to generate
    revocation links, so return ServiceAccountPermissionGrant objects that include the mapping ID.
    """
    grants = session.query(
        User.username,
        Permission.name,
        ServiceAccountPermissionMap.argument,
        ServiceAccountPermissionMap.granted_on,
        ServiceAccountPermissionMap.id,
    ).filter(
        Permission.id == ServiceAccountPermissionMap.permission_id,
        ServiceAccountPermissionMap.service_account_id == service_account.id,
        ServiceAccountPermissionMap.service_account_id == ServiceAccount.id,
        ServiceAccount.user_id == User.id,
        User.enabled == True,
    )
    out = []
    for grant in grants:
        out.append(
            ServiceAccountPermissionGrant(
                service_account=grant.username,
                permission=grant.name,
                argument=grant.argument,
                granted_on=grant.granted_on,
                is_alias=False,
                grant_id=grant.id,
            )
        )
    return out


def all_service_account_permissions(session):
    # type: (Session) -> Dict[str, List[ServiceAccountPermissionGrant]]
    """Return a dict of service account names to their permissions."""
    grants = session.query(
        User.username,
        Permission.name,
        ServiceAccountPermissionMap.argument,
        ServiceAccountPermissionMap.granted_on,
        ServiceAccountPermissionMap.id,
    ).filter(
        Permission.id == ServiceAccountPermissionMap.permission_id,
        ServiceAccountPermissionMap.service_account_id == ServiceAccount.id,
        ServiceAccount.user_id == User.id,
        User.enabled == True,
    )
    out = defaultdict(list)  # type: Dict[str, List[ServiceAccountPermissionGrant]]
    for grant in grants:
        out[grant.username].append(
            ServiceAccountPermissionGrant(
                service_account=grant.username,
                permission=grant.name,
                argument=grant.argument,
                granted_on=grant.granted_on,
                is_alias=False,
                grant_id=grant.id,
            )
        )
    return out
