from sqlalchemy.exc import IntegrityError

from grouper.constants import (
    GROUP_ADMIN,
    PERMISSION_ADMIN,
    PERMISSION_AUDITOR,
    SYSTEM_PERMISSIONS,
    USER_ADMIN,
)
from grouper.ctl.util import make_session
from grouper.models.base.model_base import Model
from grouper.models.base.session import get_db_engine
from grouper.models.group import Group
from grouper.permissions import create_permission, get_permission, grant_permission
from grouper.settings import settings
from grouper.util import get_auditors_group_name, get_database_url


def sync_db_command(args):
    # Models not implicitly or explictly imported above are explicitly imported here
    from grouper.models.perf_profile import PerfProfile  # noqa: F401
    from grouper.models.user_token import UserToken      # noqa: F401

    db_engine = get_db_engine(get_database_url(settings))
    Model.metadata.create_all(db_engine)

    # Add some basic database structures we know we will need if they don't exist.
    session = make_session()

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

    auditors_group_name = get_auditors_group_name(settings)
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
            raise Exception("Failed to create group: {}".format(auditors_group_name))

        permission = get_permission(session, PERMISSION_AUDITOR)
        assert permission, "Permission should have been created earlier!"
        grant_permission(session, auditors_group.id, permission.id)

        session.commit()


def add_parser(subparsers):
    sync_db_parser = subparsers.add_parser("sync_db", help="Apply database schema to database.")
    sync_db_parser.set_defaults(func=sync_db_command)
