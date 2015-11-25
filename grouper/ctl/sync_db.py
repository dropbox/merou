from sqlalchemy.exc import IntegrityError

from grouper.constants import SYSTEM_PERMISSIONS
from grouper.ctl.util import make_session
from grouper.models import (
        get_db_engine,
        Group,
        Model,
        Permission,
        )
from grouper.settings import settings
from grouper.util import get_database_url


def sync_db_command(args):
    db_engine = get_db_engine(get_database_url(settings))
    Model.metadata.create_all(db_engine)

    # Add some basic database structures we know we will need if they don't exist.
    session = make_session()
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
    admin_group_permission_names = [perm[1] for perm in admin_group.my_permissions()]

    for name, description in SYSTEM_PERMISSIONS:
        permission = Permission.get(session, name)
        if permission and name not in admin_group_permission_names:
            try:
                admin_group.grant_permission(permission)
                session.commit()
            except IntegrityError:
                # The permission is already extant in the group, carry on.
                session.rollback()
            continue
        elif permission:
            continue

        permission = Permission(name=name, description=description)
        try:
            permission.add(session)
            session.flush()
        except IntegrityError:
            session.rollback()
            raise Exception('Failed to create permission: %s' % (name, ))
        session.commit()
        admin_group.grant_permission(permission)
        session.commit()

    session.commit()


def add_parser(subparsers):
    sync_db_parser = subparsers.add_parser("sync_db", help="Apply database schema to database.")
    sync_db_parser.set_defaults(func=sync_db_command)
