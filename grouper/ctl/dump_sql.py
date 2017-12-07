from typing import TYPE_CHECKING

from sqlalchemy.schema import CreateTable

from grouper.models.base.model_base import Model
from grouper.models.base.session import get_db_engine
from grouper.settings import settings
from grouper.util import get_database_url

if TYPE_CHECKING:
    import argparse  # noqa


def dump_sql_command(args):
    # type: (argparse.Namespace) -> None
    db_engine = get_db_engine(get_database_url(settings))
    for table in Model.metadata.sorted_tables:
        print CreateTable(table).compile(db_engine)


def add_parser(subparsers):
    # type: (argparse._SubParsersAction) -> None
    dump_sql_parser = subparsers.add_parser("dump_sql", help="Dump database schema.")
    dump_sql_parser.set_defaults(func=dump_sql_command)
