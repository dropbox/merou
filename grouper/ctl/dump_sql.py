from __future__ import print_function

from typing import TYPE_CHECKING

from sqlalchemy.schema import CreateIndex, CreateTable

from grouper.models.base.model_base import Model
from grouper.models.base.session import get_db_engine

if TYPE_CHECKING:
    from argparse import _SubParsersAction, Namespace
    from grouper.ctl.settings import CtlSettings
    from grouper.repositories.factory import SessionFactory


def dump_sql_command(args, settings, session_factory):
    # type: (Namespace, CtlSettings, SessionFactory) -> None
    db_engine = get_db_engine(settings.database_url)
    for table in Model.metadata.sorted_tables:
        print(CreateTable(table).compile(db_engine))
        for index in table.indexes:
            print(CreateIndex(index).compile(db_engine))


def add_parser(subparsers):
    # type: (_SubParsersAction) -> None
    dump_sql_parser = subparsers.add_parser("dump_sql", help="Dump database schema.")
    dump_sql_parser.set_defaults(func=dump_sql_command)
