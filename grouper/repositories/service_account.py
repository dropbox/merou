from typing import TYPE_CHECKING

from grouper.entities.group import GroupNotFoundException
from grouper.entities.service_account import ServiceAccountNotFoundException
from grouper.entities.user import UserNotFoundException
from grouper.models.group import Group
from grouper.models.group_service_accounts import GroupServiceAccount
from grouper.models.service_account import ServiceAccount as SQLServiceAccount
from grouper.models.user import User as SQLUser

if TYPE_CHECKING:
    from grouper.models.base.session import Session


class ServiceAccountRepository(object):
    """Storage layer for service accounts."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def assign_service_account_to_group(self, name, groupname):
        # type: (str, str) -> None
        service_account = SQLServiceAccount.get(self.session, name=name)
        if not service_account:
            raise ServiceAccountNotFoundException(name)

        group = Group.get(self.session, name=groupname)
        if not group:
            raise GroupNotFoundException(groupname)

        existing_relationship = GroupServiceAccount.get(
            self.session, service_account_id=service_account.id
        )
        if existing_relationship:
            existing_relationship.group_id = group.id
        else:
            group_service_account = GroupServiceAccount(
                group_id=group.id, service_account_id=service_account.id
            )
            group_service_account.add(self.session)

    def enable_service_account(self, name):
        # type: (str) -> None
        service_account = SQLServiceAccount.get(self.session, name=name)
        if not service_account:
            raise ServiceAccountNotFoundException(name)

        service_account.user.enabled = True

    def mark_disabled_user_as_service_account(self, name, description="", mdbset=""):
        # type: (str, str, str) -> None
        """Transform a disabled user into a disabled, ownerless service account.

        WARNING: This function encodes the fact that the user and service account repos
        are in fact the same thing, as it assumes that a service account is just a user
        that is marked in a special way. This is a temporary breaking of the abstractions
        and will have to be cleaned up once the repositories are properly separate.
        """
        user = SQLUser.get(self.session, name=name)
        if not user:
            raise UserNotFoundException(name)

        service_account = SQLServiceAccount(
            user_id=user.id, description=description, machine_set=mdbset
        )
        service_account.add(self.session)

        user.is_service_account = True
