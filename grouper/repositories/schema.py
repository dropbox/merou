"""Manage the database schema.

SQLAlchemy schema operations through the ORM determine the list of tables through metaclasses when
a class representing a database table is created.  This means that every underlying model must be
imported when performing global schema operations, such as initializing or dropping the schema, so
that SQLAlchemy will know what tables to create or delete.

This class therefore imports *every* model to ensure SQLAlchemy has a complete view.  If any new
models are added, be sure to also add them to the import list.
"""

from io import StringIO
from typing import TYPE_CHECKING

from sqlalchemy.schema import CreateIndex, CreateTable

from grouper.models.async_notification import AsyncNotification  # noqa: F401
from grouper.models.audit import Audit  # noqa: F401
from grouper.models.audit_log import AuditLog  # noqa: F401
from grouper.models.audit_member import AuditMember  # noqa: F401
from grouper.models.base.model_base import Model
from grouper.models.base.session import get_db_engine
from grouper.models.comment import Comment  # noqa: F401
from grouper.models.counter import Counter  # noqa: F401
from grouper.models.group import Group  # noqa: F401
from grouper.models.group_edge import GroupEdge  # noqa: F401
from grouper.models.group_service_accounts import GroupServiceAccount  # noqa: F401
from grouper.models.perf_profile import PerfProfile  # noqa: F401
from grouper.models.permission import Permission  # noqa: F401
from grouper.models.permission_map import PermissionMap  # noqa: F401
from grouper.models.permission_request import PermissionRequest  # noqa: F401
from grouper.models.permission_request_status_change import (  # noqa: F401
    PermissionRequestStatusChange,
)
from grouper.models.public_key import PublicKey  # noqa: F401
from grouper.models.request import Request  # noqa: F401
from grouper.models.request_status_change import RequestStatusChange  # noqa: F401
from grouper.models.service_account import ServiceAccount  # noqa: F401
from grouper.models.service_account_permission_map import ServiceAccountPermissionMap  # noqa: F401
from grouper.models.user import User  # noqa: F401
from grouper.models.user_metadata import UserMetadata  # noqa: F401
from grouper.models.user_password import UserPassword  # noqa: F401
from grouper.models.user_token import UserToken  # noqa: F401

if TYPE_CHECKING:
    from grouper.settings import Settings


class SchemaRepository:
    """Manipulate the database schema."""

    def __init__(self, settings):
        # type: (Settings) -> None
        self.settings = settings

    def drop_schema(self):
        # type: () -> None
        """Not exposed via a service, used primarily for tests."""
        db_engine = get_db_engine(self.settings.database)
        Model.metadata.drop_all(db_engine)

    def dump_schema(self):
        # type: () -> str
        db_engine = get_db_engine(self.settings.database)
        sql = StringIO()
        for table in Model.metadata.sorted_tables:
            sql.write(str(CreateTable(table).compile(db_engine)))
            for index in table.indexes:
                sql.write(str(CreateIndex(index).compile(db_engine)))
        return sql.getvalue()

    def initialize_schema(self):
        # type: () -> None
        db_engine = get_db_engine(self.settings.database)
        Model.metadata.create_all(db_engine)
