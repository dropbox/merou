from __future__ import print_function

from typing import TYPE_CHECKING

from sqlalchemy.schema import CreateIndex, CreateTable

from grouper.models.base.model_base import Model
from grouper.models.base.session import get_db_engine
from grouper.util import get_database_url

if TYPE_CHECKING:
    from argparse import _SubParsersAction, Namespace
    from grouper.settings import Settings


def dump_sql_command(args, settings):
    # type: (Namespace, Settings) -> None
    db_engine = get_db_engine(get_database_url(settings))
    for table in Model.metadata.sorted_tables:
        print(CreateTable(table).compile(db_engine))
        for index in table.indexes:
            print(CreateIndex(index).compile(db_engine))


def add_parser(subparsers):
    # type: (_SubParsersAction) -> None
    dump_sql_parser = subparsers.add_parser("dump_sql", help="Dump database schema.")
    dump_sql_parser.set_defaults(func=dump_sql_command)
