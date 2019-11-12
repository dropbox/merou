"""Utilities to set up test cases.

Provides a SetupTest object that creates the database session, provides use case factories for
individual tests, and provides methods to create objects in the test database.  These methods try
to minimize the amount of code required to set up a test by creating new objects whenever needed.
So, for instance, one can just call:

    with setup.transaction():
        setup.add_user_to_group("user@a.co", "some-group")

without creating the user and group first, and both will be created if not present.

This is the new test setup mechanism, replacing the fixtures defined in tests.fixtures.  All new
tests should use this mechanism and not rely on standard_graph or other pytest fixtures.

Currently, most test setup work here is done via direct calls to the model.  This is only temporary
because the necessary methods are not yet available from service and repository objects.  As soon
as a facility is available from a service or repository, the setup code should call that method
instead of directly manipulating the model.  Eventually, it should just be another client of the
service and repository layers.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sshpubkeys import SSHKey

from grouper.entities.group import GroupJoinPolicy
from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.graph import GroupGraph
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.permission import Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.public_key import PublicKey
from grouper.models.service_account import ServiceAccount
from grouper.models.service_account_permission_map import ServiceAccountPermissionMap
from grouper.models.user import User
from grouper.models.user_metadata import UserMetadata
from grouper.plugin import set_global_plugin_proxy
from grouper.plugin.proxy import PluginProxy
from grouper.repositories.factory import (
    GraphRepositoryFactory,
    SessionFactory,
    SingletonSessionFactory,
    SQLRepositoryFactory,
)
from grouper.repositories.schema import SchemaRepository
from grouper.services.factory import ServiceFactory
from grouper.settings import Settings
from grouper.usecases.factory import UseCaseFactory
from tests.path_util import db_url

if TYPE_CHECKING:
    from datetime import datetime
    from py.local import LocalPath
    from typing import Iterator, Optional


class SetupTest:
    """Set up the environment for a test.

    Most actions should be done inside of a transaction, created via the transaction() method and
    used as a context handler.  This will ensure that the test setup is committed to the database
    before the test starts running.

    Attributes:
        settings: Settings object for tests (only the database is configured)
        graph: Underlying graph (not refreshed from the database automatically!)
        session: The underlying database session
        plugins: The plugin proxy used for the tests
        repository_factory: Factory for repository objects
        sql_repository_factory: Factory that returns only SQL repository objects (no graph)
        service_factory: Factory for service objects
        usecase_factory: Factory for usecase objects
    """

    def __init__(self, tmpdir):
        # type: (LocalPath) -> None
        self.settings = Settings()
        self.settings.database = db_url(tmpdir)
        self.plugins = PluginProxy([])
        self.graph = GroupGraph()

        # Reinitialize the global plugin proxy with an empty set of plugins in case a previous test
        # initialized plugins.  This can go away once a plugin proxy is injected into everything
        # that needs it instead of maintained as a global.
        set_global_plugin_proxy(self.plugins)

        self.initialize_database()
        self.open_database()

    def initialize_database(self):
        # type: () -> None
        schema_repository = SchemaRepository(self.settings)

        # If using a persistent database, clear the database first.
        if "MEROU_TEST_DATABASE" in os.environ:
            schema_repository.drop_schema()

        # Create the database schema.
        schema_repository.initialize_schema()

    def open_database(self) -> None:
        self.session = SessionFactory(self.settings).create_session()
        session_factory = SingletonSessionFactory(self.session)
        self.repository_factory = GraphRepositoryFactory(
            self.settings, self.plugins, session_factory, self.graph
        )
        self.sql_repository_factory = SQLRepositoryFactory(
            self.settings, self.plugins, session_factory
        )
        self.service_factory = ServiceFactory(self.settings, self.plugins, self.repository_factory)
        self.usecase_factory = UseCaseFactory(self.settings, self.plugins, self.service_factory)
        self._transaction_service = self.service_factory.create_transaction_service()

    def reopen_database(self) -> None:
        """Reopen the database (sometimes needed to synchronize SQLite.

        This will invalidate all existing factories and any objects created from them.  The caller
        is responsible for discarding any objects using the previous session and creating new
        objects as needed.
        """
        self.close()
        self.open_database()

    def close(self):
        # type: () -> None
        self.session.close()

    @contextmanager
    def transaction(self):
        # type: () -> Iterator[None]
        with self._transaction_service.transaction():
            yield
        self.graph.update_from_db(self.session)

    def create_group(
        self,
        name: str,
        description: str = "",
        join_policy: GroupJoinPolicy = GroupJoinPolicy.CAN_ASK,
        email: Optional[str] = None,
    ) -> None:
        """Create a group, does nothing if it already exists."""
        group_service = self.service_factory.create_group_service()
        if not group_service.group_exists(name):
            group_service.create_group(name, description, join_policy, email)

    def create_permission(
        self, name, description="", audited=False, enabled=True, created_on=None
    ):
        # type: (str, str, bool, bool, Optional[datetime]) -> None
        """Create a permission, does nothing if it already exists."""
        permission_repository = self.repository_factory.create_permission_repository()
        if not permission_repository.get_permission(name):
            permission_repository.create_permission(
                name, description, audited, enabled, created_on
            )

    def create_user(self, name):
        # type: (str) -> None
        """Create a user, does nothing if it already exists."""
        if User.get(self.session, name=name):
            return
        user = User(username=name)
        user.add(self.session)

    def add_group_to_group(self, member, group, expiration=None):
        # type: (str, str, Optional[datetime]) -> None
        self.create_group(member)
        self.create_group(group)
        member_obj = Group.get(self.session, name=member)
        assert member_obj
        group_obj = Group.get(self.session, name=group)
        assert group_obj
        edge = GroupEdge(
            group_id=group_obj.id,
            member_type=OBJ_TYPES["Group"],
            member_pk=member_obj.id,
            expiration=expiration,
            active=True,
            _role=GROUP_EDGE_ROLES.index("member"),
        )
        edge.add(self.session)

    def add_user_to_group(self, user, group, role="member", expiration=None):
        # type: (str, str, str, Optional[datetime]) -> None
        self.create_user(user)
        self.create_group(group)
        user_obj = User.get(self.session, name=user)
        assert user_obj
        group_obj = Group.get(self.session, name=group)
        assert group_obj
        edge = GroupEdge(
            group_id=group_obj.id,
            member_type=OBJ_TYPES["User"],
            member_pk=user_obj.id,
            expiration=expiration,
            active=True,
            _role=GROUP_EDGE_ROLES.index(role),
        )
        edge.add(self.session)

    def remove_user_from_group(self, user, group):
        # type: (str, str) -> None
        user_obj = User.get(self.session, name=user)
        assert user_obj
        group_obj = Group.get(self.session, name=group)
        assert group_obj
        self.session.query(GroupEdge).filter(
            GroupEdge.group_id == group_obj.id,
            GroupEdge.member_type == OBJ_TYPES["User"],
            GroupEdge.member_pk == user_obj.id,
        ).delete()

    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        self.create_group(group)
        self.create_permission(permission)
        group_service = self.service_factory.create_group_service()
        group_service.grant_permission_to_group(permission, argument, group)

    def revoke_permission_from_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        permission_obj = Permission.get(self.session, name=permission)
        assert permission_obj
        group_obj = Group.get(self.session, name=group)
        assert group_obj
        self.session.query(PermissionMap).filter(
            PermissionMap.permission_id == permission_obj.id,
            PermissionMap.group_id == group_obj.id,
            PermissionMap.argument == argument,
        ).delete()

    def create_group_request(self, user, group, role="member"):
        # type: (str, str, str) -> None
        self.create_user(user)
        self.create_group(group)

        user_obj = User.get(self.session, name=user)
        assert user_obj
        group_obj = Group.get(self.session, name=group)
        assert group_obj

        # Note: despite the function name, this only creates the request. The flow here is
        # convoluted enough that it seems best to preserve exact behavior for testing.
        group_obj.add_member(
            requester=user_obj, user_or_group=user_obj, reason="", status="pending", role=role
        )

    def create_service_account(self, service_account, owner, machine_set="", description=""):
        # type: (str, str, str, str) -> None
        self.create_group(owner)
        service_account_repository = self.repository_factory.create_service_account_repository()
        service_account_repository.create_service_account(
            service_account, owner, machine_set, description
        )

    def grant_permission_to_service_account(self, permission, argument, service_account):
        # type: (str, str, str) -> None
        self.create_permission(permission)
        permission_grant_repository = self.repository_factory.create_permission_grant_repository()
        permission_grant_repository.grant_permission_to_service_account(
            permission, argument, service_account
        )

    def add_metadata_to_user(self, key, value, user):
        # type: (str, str, str) -> None
        sql_user = User.get(self.session, name=user)
        assert sql_user
        metadata = UserMetadata(user_id=sql_user.id, data_key=key, data_value=value)
        metadata.add(self.session)

    def add_public_key_to_user(self, key, user):
        # type: (str, str) -> None
        sql_user = User.get(self.session, name=user)
        assert sql_user
        public_key = SSHKey(key, strict=True)
        public_key.parse()
        sql_public_key = PublicKey(
            user_id=sql_user.id,
            public_key=public_key.keydata.strip(),
            fingerprint=public_key.hash_md5().replace("MD5:", ""),
            fingerprint_sha256=public_key.hash_sha256().replace("SHA256:", ""),
            key_size=public_key.bits,
            key_type=public_key.key_type,
            comment=public_key.comment,
        )
        sql_public_key.add(self.session)

    def disable_user(self, user):
        # type: (str) -> None
        user_repository = self.repository_factory.create_user_repository()
        user_repository.disable_user(user)

    def disable_group(self, group):
        # type: (str) -> None
        group_obj = Group.get(self.session, name=group)
        assert group_obj
        group_obj.enabled = False

    def disable_service_account(self, service_account):
        # type: (str) -> None
        service_obj = ServiceAccount.get(self.session, name=service_account)
        assert service_obj
        service_obj.user.enabled = False
        service_obj.owner.delete(self.session)
        permissions = self.session.query(ServiceAccountPermissionMap).filter_by(
            service_account_id=service_obj.id
        )
        for permission in permissions:
            permission.delete(self.session)

    def create_role_user(self, role_user, description="", join_policy=GroupJoinPolicy.CAN_ASK):
        # type: (str, str, GroupJoinPolicy) -> None
        """Create an old-style role user.

        This concept is obsolete and all code related to it will be deleted once all remaining
        legacy role users have been converted to service accounts.  This method should be used only
        for tests to maintain backward compatibility until that happens.
        """
        user = User(username=role_user, role_user=True)
        user.add(self.session)
        self.create_group(role_user, description, join_policy)
        self.add_user_to_group(role_user, role_user)
