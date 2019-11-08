import os
from datetime import datetime
from time import time
from typing import TYPE_CHECKING

import pytest

from grouper.api.main import create_api_application
from grouper.api.settings import ApiSettings
from grouper.app import GrouperApplication
from grouper.constants import (
    AUDIT_MANAGER,
    AUDIT_VIEWER,
    GROUP_ADMIN,
    PERMISSION_ADMIN,
    PERMISSION_AUDITOR,
    USER_ADMIN,
)
from grouper.fe.main import create_fe_application
from grouper.fe.settings import FrontendSettings
from grouper.graph import Graph
from grouper.group_service_account import add_service_account
from grouper.initialization import create_graph_usecase_factory
from grouper.models.base.model_base import Model
from grouper.models.base.session import get_db_engine, Session
from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User
from grouper.permissions import enable_permission_auditing
from grouper.plugin import set_global_plugin_proxy
from grouper.plugin.proxy import PluginProxy
from grouper.repositories.factory import SingletonSessionFactory
from grouper.settings import set_global_settings, Settings
from tests.path_util import db_url
from tests.util import add_member, grant_permission

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from pytest import FixtureRequest
    from py.local import LocalPath
    from typing import Dict


@pytest.fixture
def standard_graph(session, graph, users, groups, service_accounts, permissions):
    """Setup a standard graph used for many tests. In graph form:

    +-----------------------+
    |                       |
    |  team-sre             |
    |    * gary (o)         +---------------------------------+
    |    * zay              |                                 |
    |    * zorkian          |                                 |
    |    * service (s)      |                     +-----------v-----------+
    |                       |                     |                       |
    +-----------------------+                     |  serving-team         |
    +-----------------------+           +--------->    * zorkian (o)      |
    |                       |           |         |                       |
    |  tech-ops             |           |         +-----------+-----------+
    |    * zay (o)          |           |                     |
    |    * gary             +-----------+                     |
    |    * figurehead (np)  |                                 |
    |                       |                                 |
    +-----------------------+                                 |
    +-----------------------+                     +-----------v-----------+
    |                       |                     |                       |
    |  security-team        |                     |  team-infra           |
    |    * oliver (o)       +--------------------->    * gary (o)         |
    |    * figurehead       |                     |                       |
    |                       |                     +-----------+-----------+
    +-----------------------+                                 |
    +-----------------------+                                 |
    |                       |                                 |
    |  sad-team             |                                 |
    |    * zorkian (o)      |                                 |
    |    * oliver           |                     +-----------v-----------+
    |                       |                     |                       |
    +-----------------------+                     |  all-teams            |
    +-----------------------+                     |    * testuser (o)     |
    |                       |                     |                       |
    |  audited-team         |                     +-----------------------+
    |    * zorkian (o)      |
    |                       |
    +-----------------------+
    +-----------------------+
    |                       |
    |  auditors             |
    |    * zorkian (o)      |
    |                       |
    +-----------------------+
    +-----------------------+
    |                       |
    |  user-admins          |
    |    * tyleromeara (o)  |
    |    * cbguder (o)      |
    |                       |
    +-----------------------+
    +-----------------------+
    |                       |
    |  group-admins         |
    |    * cbguder (o)      |
    |                       |
    +-----------------------+
    +-----------------------+
    |                       |
    |  permission-admins    |
    |    * gary (o)         |
    |    * cbguder          |
    |                       |
    +-----------------------+

    Arrows denote member of the source in the destination group. (o) for
    owners, (np) for non-permissioned owners, (s) for service accounts.
    """
    add_member(groups["team-sre"], users["gary@a.co"], role="owner")
    add_member(groups["team-sre"], users["zay@a.co"])
    add_member(groups["team-sre"], users["zorkian@a.co"])
    grant_permission(groups["team-sre"], permissions["ssh"], argument="*")
    grant_permission(groups["team-sre"], permissions["team-sre"], argument="*")

    add_member(groups["serving-team"], users["zorkian@a.co"], role="owner")
    add_member(groups["serving-team"], groups["team-sre"])
    add_member(groups["serving-team"], groups["tech-ops"])
    grant_permission(groups["serving-team"], permissions["audited"])

    add_member(groups["tech-ops"], users["zay@a.co"], role="owner")
    add_member(groups["tech-ops"], users["gary@a.co"])
    add_member(groups["tech-ops"], users["figurehead@a.co"], role="np-owner")
    grant_permission(groups["tech-ops"], permissions["ssh"], argument="shell")

    add_member(groups["security-team"], users["oliver@a.co"], role="owner")
    add_member(groups["security-team"], users["figurehead@a.co"], role="member")

    add_member(groups["sad-team"], users["zorkian@a.co"], role="owner")
    add_member(groups["sad-team"], users["oliver@a.co"])
    grant_permission(groups["sad-team"], permissions["owner"], argument="sad-team")

    add_member(groups["audited-team"], users["zorkian@a.co"], role="owner")
    grant_permission(groups["audited-team"], permissions["audited"])

    add_member(groups["team-infra"], users["gary@a.co"], role="owner")
    add_member(groups["team-infra"], groups["serving-team"])
    add_member(groups["team-infra"], groups["security-team"])
    grant_permission(groups["team-infra"], permissions["sudo"], argument="shell")

    add_member(groups["auditors"], users["zorkian@a.co"], role="owner")
    grant_permission(groups["auditors"], permissions[AUDIT_VIEWER])
    grant_permission(groups["auditors"], permissions[AUDIT_MANAGER])
    grant_permission(groups["auditors"], permissions[PERMISSION_AUDITOR])

    add_member(groups["all-teams"], users["testuser@a.co"], role="owner")
    add_member(groups["all-teams"], groups["team-infra"])

    add_member(groups["user-admins"], users["tyleromeara@a.co"], role="owner")
    add_member(groups["user-admins"], users["cbguder@a.co"], role="owner")
    grant_permission(groups["user-admins"], permissions[USER_ADMIN])

    add_member(groups["group-admins"], users["cbguder@a.co"], role="owner")
    grant_permission(groups["group-admins"], permissions[GROUP_ADMIN])

    add_member(groups["permission-admins"], users["gary@a.co"], role="owner")
    add_member(groups["permission-admins"], users["cbguder@a.co"], role="member")
    grant_permission(groups["permission-admins"], permissions[PERMISSION_ADMIN])

    session.commit()
    graph.update_from_db(session)

    return graph


@pytest.fixture
def session(request, tmpdir):
    # type: (FixtureRequest, LocalPath) -> None
    settings = Settings()
    set_global_settings(settings)

    # Reinitialize plugins in case a previous test configured some.
    set_global_plugin_proxy(PluginProxy([]))

    db_engine = get_db_engine(db_url(tmpdir))

    # Clean up from previous tests if using a persistent database.
    if "MEROU_TEST_DATABASE" in os.environ:
        Model.metadata.drop_all(db_engine)

    # Create the database schema and the corresponding session.
    Model.metadata.create_all(db_engine)
    Session.configure(bind=db_engine)
    session = Session()

    def fin():
        # type: () -> None
        """Explicitly close the session to avoid any dangling transactions."""
        session.close()

    request.addfinalizer(fin)
    return session


@pytest.fixture
def graph(session):
    graph = Graph()
    graph.update_from_db(session)
    return graph


@pytest.fixture
def users(session):
    users = {
        username: User.get_or_create(session, username=username)[0]
        for username in (
            "gary@a.co",
            "zay@a.co",
            "zorkian@a.co",
            "oliver@a.co",
            "testuser@a.co",
            "figurehead@a.co",
            "zebu@a.co",
            "tyleromeara@a.co",
            "cbguder@a.co",
        )
    }
    users["role@a.co"] = User.get_or_create(session, username="role@a.co", role_user=True)[0]
    session.commit()
    return users


@pytest.fixture
def groups(session):
    groups = {
        groupname: Group.get_or_create(session, groupname=groupname)[0]
        for groupname in (
            "team-sre",
            "tech-ops",
            "team-infra",
            "all-teams",
            "serving-team",
            "security-team",
            "auditors",
            "sad-team",
            "audited-team",
            "user-admins",
            "group-admins",
            "permission-admins",
            "role@a.co",  # group for a role user
        )
    }
    groups_with_emails = ("team-sre", "serving-team", "security-team")
    for group in groups_with_emails:
        groups[group].email_address = "{}@a.co".format(group)
    session.commit()
    return groups


@pytest.fixture
def service_accounts(session, users, groups):
    user = User(username="service@a.co", is_service_account=True)
    service_account = ServiceAccount(
        user=user, description="some service account", machine_set="some machines"
    )
    user.add(session)
    service_account.add(session)
    session.flush()
    add_service_account(session, groups["team-sre"], service_account)

    return {"service@a.co": service_account}


@pytest.fixture
def permissions(session, users):
    # type: (Session, Dict[str, User]) -> Dict[str, Permission]
    """Create a standard set of test permissions.

    Go to a bit of effort to use unique timestamps for the creation date of permissions, since it
    makes it easier to test sorting.  Similarly, don't sort the list of permissions to create by
    name so that the date sort and the name sort are different.

    Do not use milliseconds in the creation timestamps, since the result will be different in
    SQLite (where they are preserved) and MySQL (where they are stripped).
    """
    all_permissions = [
        "owner",
        "ssh",
        "sudo",
        "audited",
        AUDIT_MANAGER,
        AUDIT_VIEWER,
        PERMISSION_AUDITOR,
        PERMISSION_ADMIN,
        "team-sre",
        USER_ADMIN,
        GROUP_ADMIN,
    ]

    created_on_seconds = int(time() - 1000)
    permissions = {}
    for name in all_permissions:
        permission = Permission.get(session, name=name)
        if not permission:
            created_on = datetime.utcfromtimestamp(created_on_seconds)
            created_on_seconds += 1
            description = "{} permission".format(name)
            permission = Permission(name=name, description=description, created_on=created_on)
            permission.add(session)
        permissions[name] = permission

    enable_permission_auditing(session, permissions["audited"].name, users["zorkian@a.co"].id)

    return permissions


@pytest.fixture
def api_app(session, standard_graph):
    # type: (Session, GroupGraph) -> GrouperApplication
    settings = ApiSettings()
    set_global_settings(settings)
    session_factory = SingletonSessionFactory(session)
    plugins = PluginProxy([])
    set_global_plugin_proxy(plugins)
    usecase_factory = create_graph_usecase_factory(
        settings, plugins, session_factory, standard_graph
    )
    return create_api_application(standard_graph, settings, plugins, usecase_factory)


@pytest.fixture
def fe_app(session, standard_graph, tmpdir):
    # type: (Session, GroupGraph, LocalPath) -> GrouperApplication
    settings = FrontendSettings()
    set_global_settings(settings)
    return create_fe_application(settings, "", xsrf_cookies=False, session=lambda: session)
