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

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

from grouper.entities.group import GroupJoinPolicy
from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.graph import GroupGraph
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.group_service_accounts import GroupServiceAccount
from grouper.models.permission import Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.service_account import ServiceAccount
from grouper.models.service_account_permission_map import ServiceAccountPermissionMap
from grouper.models.user import User
from grouper.plugin import set_global_plugin_proxy
from grouper.plugin.proxy import PluginProxy
from grouper.repositories.factory import (
    GraphRepositoryFactory,
    SessionFactory,
    SingletonSessionFactory,
)
from grouper.repositories.schema import SchemaRepository
from grouper.services.factory import ServiceFactory
from grouper.settings import Settings
from grouper.usecases.factory import UseCaseFactory
from tests.path_util import db_url

if TYPE_CHECKING:
    from datetime import datetime
    from grouper.models.base.session import Session
    from py.local import LocalPath
    from typing import Iterator, Optional


class SetupTest(object):
    """Set up the environment for a test.

    Most actions should be done inside of a transaction, created via the transaction() method and
    used as a context handler.  This will ensure that the test setup is committed to the database
    before the test starts running.

    Attributes:
        settings: Settings object for tests (only the database is configured)
        graph: Underlying graph (not refreshed from the database automatically!)
        session: The underlying database session
        repository_factory: Factory for repository objects
        service_factory: Factory for service objects
        usecase_factory: Factory for usecase objects
    """

    def __init__(self, tmpdir):
        # type: (LocalPath) -> None
        self.settings = Settings()
        self.settings.database = db_url(tmpdir)

        self.initialize_database()

        # Reinitialize the global plugin proxy with an empty set of plugins in case a previous test
        # initialized plugins.  This can go away once a plugin proxy is injected into everything
        # that needs it instead of maintained as a global.
        set_global_plugin_proxy(PluginProxy([]))

        self.session = SessionFactory(self.settings).create_session()
        self.graph = GroupGraph()
        self.repository_factory = GraphRepositoryFactory(
            self.settings, PluginProxy([]), SingletonSessionFactory(self.session), self.graph
        )
        self.service_factory = ServiceFactory(self.repository_factory)
        self.usecase_factory = UseCaseFactory(self.settings, self.service_factory)
        self._transaction_service = self.service_factory.create_transaction_service()

    def initialize_database(self):
        # type: () -> Session
        schema_repository = SchemaRepository(self.settings)

        # If using a persistent database, clear the database first.
        if "MEROU_TEST_DATABASE" in os.environ:
            schema_repository.drop_schema()

        # Create the database schema.
        schema_repository.initialize_schema()

    def close(self):
        # type: () -> None
        self.session.close()

    @contextmanager
    def transaction(self):
        # type: () -> Iterator[None]
        with self._transaction_service.transaction():
            yield
        self.graph.update_from_db(self.session)

    def create_group(self, name, description="", join_policy=GroupJoinPolicy.CAN_ASK):
        # type: (str, str, GroupJoinPolicy) -> None
        """Create a group, does nothing if it already exists."""
        group_service = self.service_factory.create_group_service()
        if not group_service.group_exists(name):
            group_service.create_group(name, description, join_policy)

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

    def create_service_account(self, service_account, owner, description="", machine_set=""):
        # type: (str, str, str, str) -> None
        self.create_group(owner)
        group_obj = Group.get(self.session, name=owner)
        assert group_obj

        if User.get(self.session, name=service_account):
            return
        user = User(username=service_account)
        user.add(self.session)
        service_account_obj = ServiceAccount(
            user_id=user.id, description=description, machine_set=machine_set
        )
        service_account_obj.add(self.session)
        user.is_service_account = True

        self.session.flush()
        owner_map = GroupServiceAccount(
            group_id=group_obj.id, service_account_id=service_account_obj.id
        )
        owner_map.add(self.session)

    def grant_permission_to_service_account(self, permission, argument, service_account):
        # type: (str, str, str) -> None
        self.create_permission(permission)
        permission_obj = Permission.get(self.session, name=permission)
        assert permission_obj
        user_obj = User.get(self.session, name=service_account)
        assert user_obj, "Must create the service account first"
        assert user_obj.is_service_account
        grant = ServiceAccountPermissionMap(
            permission_id=permission_obj.id,
            service_account_id=user_obj.service_account.id,
            argument=argument,
        )
        grant.add(self.session)

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
