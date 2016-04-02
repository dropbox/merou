from sqlalchemy.exc import IntegrityError

from grouper.constants import (
        GROUP_ADMIN,
        PERMISSION_ADMIN,
        SYSTEM_PERMISSIONS,
        USER_ADMIN,
        )
from grouper.ctl.util import make_session
from grouper.model_soup import Group
from grouper.models.base.session import get_db_engine
from grouper.settings import settings
from grouper.util import get_database_url
from grouper.models.base.model_base import Model
from grouper.permissions import grant_permission
from grouper.models.permission import Permission


def sync_db_command(args):
    db_engine = get_db_engine(get_database_url(settings))
    Model.metadata.create_all(db_engine)

    # Add some basic database structures we know we will need if they don't exist.
    session = make_session()

    for name, description in SYSTEM_PERMISSIONS:
        test = Permission.get(session, name)
        if test:
            continue
        permission = Permission(name=name, description=description)
        try:
            permission.add(session)
            session.flush()
        except IntegrityError:
            session.rollback()
            raise Exception('Failed to create permission: %s' % (name, ))
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
            raise Exception('Failed to create group: grouper-administrators')

        for permission_name in (GROUP_ADMIN, PERMISSION_ADMIN, USER_ADMIN):
            permission = Permission.get(session, permission_name)
            assert permission, "Permission should have been created earlier!"
            grant_permission(session, admin_group.id, permission.id)

        session.commit()


def add_parser(subparsers):
    sync_db_parser = subparsers.add_parser("sync_db", help="Apply database schema to database.")
    sync_db_parser.set_defaults(func=sync_db_command)
