from sqlalchemy.exc import IntegrityError

from grouper.constants import SYSTEM_PERMISSIONS
from grouper.ctl.util import make_session
from grouper.models import (
        get_db_engine,
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


def add_parser(subparsers):
    sync_db_parser = subparsers.add_parser("sync_db", help="Apply database schema to database.")
    sync_db_parser.set_defaults(func=sync_db_command)
