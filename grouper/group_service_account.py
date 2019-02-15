import logging
from typing import TYPE_CHECKING

from grouper.models.counter import Counter
from grouper.models.group_service_accounts import GroupServiceAccount
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User

if TYPE_CHECKING:
    from grouper.models.group import Group
    from grouper.models.session import Session
    from typing import List


def add_service_account(session, group, service_account):
    # type: (Session, Group, ServiceAccount) -> None
    """Add a service account to a group."""
    logging.debug(
        "Adding service account %s to %s", service_account.user.username, group.groupname
    )
    GroupServiceAccount(group_id=group.id, service_account=service_account).add(session)
    Counter.incr(session, "updates")
    session.commit()


def get_service_accounts(session, group):
    # type: (Session, Group) -> List[ServiceAccount]
    """Return all service accounts owned by a group."""

    service_accounts = (
        session.query(ServiceAccount)
        .join(ServiceAccount.owner)
        .filter(
            GroupServiceAccount.group_id == group.id,
            GroupServiceAccount.service_account_id == ServiceAccount.id,
            group.enabled == True,
            User.enabled == True,
        )
        .all()
    )

    return service_accounts
