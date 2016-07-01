import pytest

from grouper import model_soup
from grouper.api.routes import HANDLERS as API_HANDLERS
from grouper.app import Application
from grouper.constants import AUDIT_MANAGER, PERMISSION_AUDITOR
from grouper.fe.routes import HANDLERS as FE_HANDLERS
from grouper.fe.template_util import get_template_env
from grouper.graph import Graph
from grouper.model_soup import Group
from grouper.models.base.model_base import Model
from grouper.models.base.session import Session, get_db_engine
from grouper.models.user import User
from grouper.permissions import enable_permission_auditing
from util import add_member, grant_permission
from grouper.models.permission import Permission


@pytest.fixture
def standard_graph(session, graph, users, groups, permissions):
    """Setup a standard graph used for many tests. In graph form:

    +-----------------------+
    |                       |
    |  team-sre             |
    |    * gary (o)         +---------------------------------+
    |    * zay              |                                 |
    |    * zorkian          |                     +-----------v-----------+
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
    |                       |
    +-----------------------+
    +-----------------------+
    |                       |
    |  auditors             |
    |    * zorkian (o)      |
    |                       |
    +-----------------------+

    Arrows denote member of the source in the destination group. (o) for
    owners, (np) for non-permissioned owners.
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

    add_member(groups["audited-team"], users["zorkian@a.co"], role="owner")
    grant_permission(groups["audited-team"], permissions["audited"])

    add_member(groups["team-infra"], users["gary@a.co"], role="owner")
    add_member(groups["team-infra"], groups["serving-team"])
    add_member(groups["team-infra"], groups["security-team"])
    grant_permission(groups["team-infra"], permissions["sudo"], argument="shell")

    add_member(groups["auditors"], users["zorkian@a.co"], role="owner")
    grant_permission(groups["auditors"], permissions[AUDIT_MANAGER])
    grant_permission(groups["auditors"], permissions[PERMISSION_AUDITOR])

    add_member(groups["all-teams"], users["testuser@a.co"], role="owner")
    add_member(groups["all-teams"], groups["team-infra"])

    session.commit()
    graph.update_from_db(session)

    return graph


@pytest.fixture
def session(request, tmpdir):
    db_path = tmpdir.join("grouper.sqlite")
    db_engine = get_db_engine("sqlite:///%s" % db_path)

    Model.metadata.create_all(db_engine)
    Session.configure(bind=db_engine)
    session = Session()

    def fin():
        session.close()
        # Useful if testing against MySQL
        # model_soup.Model.metadata.drop_all(db_engine)
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
        for username in ("gary@a.co", "zay@a.co", "zorkian@a.co", "oliver@a.co", "testuser@a.co",
                "figurehead@a.co", "zebu@a.co")
    }
    users["role@a.co"] = User.get_or_create(session, username="role@a.co", role_user=True)[0]
    session.commit()
    return users


@pytest.fixture
def groups(session):
    groups = {
        groupname: Group.get_or_create(session, groupname=groupname)[0]
        for groupname in ("team-sre", "tech-ops", "team-infra", "all-teams", "serving-team",
                          "security-team", "auditors", "sad-team", "audited-team")
    }
    session.commit()
    return groups


@pytest.fixture
def permissions(session, users):
    permissions = {
        permission: Permission.get_or_create(
            session, name=permission, description="{} permission".format(permission))[0]
        for permission in ("ssh", "sudo", "audited", AUDIT_MANAGER, PERMISSION_AUDITOR, "team-sre")
    }

    enable_permission_auditing(session, permissions["audited"].name, users['zorkian@a.co'].id)

    return permissions


@pytest.fixture
def api_app(standard_graph):
    my_settings = {
            "graph": standard_graph,
            }
    return Application(API_HANDLERS, my_settings=my_settings)


@pytest.fixture
def fe_app(session, standard_graph):
    my_settings = {
            "db_session": lambda: session,
            "template_env": get_template_env(),
            }
    return Application(FE_HANDLERS, my_settings=my_settings)
