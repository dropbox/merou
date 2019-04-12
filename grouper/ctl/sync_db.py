from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from grouper.constants import (
    GROUP_ADMIN,
    PERMISSION_ADMIN,
    PERMISSION_AUDITOR,
    SYSTEM_PERMISSIONS,
    USER_ADMIN,
)
from grouper.ctl.base import CtlCommand
from grouper.ctl.util import make_session
from grouper.models.group import Group
from grouper.permissions import create_permission, get_permission, grant_permission
from grouper.util import get_auditors_group_name

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from grouper.ctl.settings import CtlSettings
    from grouper.usecases.factory import UseCaseFactory


class SyncDbCommand(CtlCommand):
    """Commands to initialize the database."""

    @staticmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
        return

    def __init__(self, settings, usecase_factory):
        # type: (CtlSettings, UseCaseFactory) -> None
        self.settings = settings
        self.usecase_factory = usecase_factory

    def run(self, args):
        # type: (Namespace) -> None
        usecase = self.usecase_factory.create_initialize_schema_usecase()
        usecase.initialize_schema()

        # TODO(rra): The code below will move into use cases later.

        # Add some basic database structures we know we will need if they don't exist.
        session = make_session(self.settings)

        for name, description in SYSTEM_PERMISSIONS:
            test = get_permission(session, name)
            if test:
                continue
            try:
                create_permission(session, name, description)
                session.flush()
            except IntegrityError:
                session.rollback()
                raise Exception("Failed to create permission: %s" % (name,))
            session.commit()

        # This group is needed to bootstrap a Grouper installation.
        admin_group = Group.get(session, name="grouper-administrators")
        if not admin_group:
            admin_group = Group(
                groupname="grouper-administrators",
                description="Administrators of the Grouper system.",
                canjoin="nobody",
            )

            try:
                admin_group.add(session)
                session.flush()
            except IntegrityError:
                session.rollback()
                raise Exception("Failed to create group: grouper-administrators")

            for permission_name in (GROUP_ADMIN, PERMISSION_ADMIN, USER_ADMIN):
                permission = get_permission(session, permission_name)
                assert permission, "Permission should have been created earlier!"
                grant_permission(session, admin_group.id, permission.id)

            session.commit()

        auditors_group_name = get_auditors_group_name(self.settings)
        auditors_group = Group.get(session, name=auditors_group_name)
        if not auditors_group:
            auditors_group = Group(
                groupname=auditors_group_name,
                description="Group for auditors, who can be owners of audited groups.",
                canjoin="canjoin",
            )

            try:
                auditors_group.add(session)
                session.flush()
            except IntegrityError:
                session.rollback()
                raise Exception("Failed to create group: {}".format(self.settings.auditors_group))

            permission = get_permission(session, PERMISSION_AUDITOR)
            assert permission, "Permission should have been created earlier!"
            grant_permission(session, auditors_group.id, permission.id)

            session.commit()
