import pytest
from selenium import webdriver
import subprocess
import yaml

from grouper.api.routes import HANDLERS as API_HANDLERS
from grouper.app import Application
from grouper.constants import AUDIT_MANAGER, GROUP_ADMIN, PERMISSION_AUDITOR, USER_ADMIN
from grouper.fe.routes import HANDLERS as FE_HANDLERS
from grouper.fe.template_util import get_template_env
from grouper.graph import Graph
from grouper.models.base.model_base import Model
from grouper.models.base.session import Session, get_db_engine
from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.models.user import User
from grouper.permissions import enable_permission_auditing
from path_util import src_path, db_url
from util import add_member, grant_permission


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

    add_member(groups["user-admins"], users["tyleromeara@a.co"], role="owner")
    add_member(groups["user-admins"], users["cbguder@a.co"], role="owner")
    grant_permission(groups["user-admins"], permissions[USER_ADMIN])

    add_member(groups["group-admins"], users["cbguder@a.co"], role="owner")
    grant_permission(groups["group-admins"], permissions[GROUP_ADMIN])

    session.commit()
    graph.update_from_db(session)

    return graph


@pytest.fixture
def session(request, tmpdir):
    db_engine = get_db_engine(db_url(tmpdir))

    Model.metadata.create_all(db_engine)
    Session.configure(bind=db_engine)
    session = Session()

    def fin():
        session.close()
        # Useful if testing against MySQL
        # Model.metadata.drop_all(db_engine)
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
                "figurehead@a.co", "zebu@a.co", "tyleromeara@a.co", "cbguder@a.co")
    }
    users["role@a.co"] = User.get_or_create(session, username="role@a.co", role_user=True)[0]
    session.commit()
    return users


@pytest.fixture
def groups(session):
    groups = {
        groupname: Group.get_or_create(session, groupname=groupname)[0]
        for groupname in ("team-sre", "tech-ops", "team-infra", "all-teams", "serving-team",
                          "security-team", "auditors", "sad-team", "audited-team", "user-admins",
                          "group-admins")
    }
    session.commit()
    return groups


@pytest.fixture
def permissions(session, users):
    permissions = {
        permission: Permission.get_or_create(
            session, name=permission, description="{} permission".format(permission))[0]
        for permission in ("ssh", "sudo", "audited", AUDIT_MANAGER, PERMISSION_AUDITOR, "team-sre",
            USER_ADMIN, GROUP_ADMIN)
    }

    enable_permission_auditing(session, permissions["audited"].name, users['zorkian@a.co'].id)

    return permissions


@pytest.fixture
def api_app(session, standard_graph):
    my_settings = {
            "graph": standard_graph,
            "db_session": lambda: session,
            }
    return Application(API_HANDLERS, my_settings=my_settings)


@pytest.fixture
def fe_app(session, standard_graph):
    my_settings = {
            "db_session": lambda: session,
            "template_env": get_template_env(),
            }
    return Application(FE_HANDLERS, my_settings=my_settings)


@pytest.yield_fixture
def async_server(standard_graph, tmpdir):
    config_path = _write_test_config(tmpdir)

    cmds = [
        [
            src_path("bin", "grouper-ctl"),
            "-vvc",
            config_path,
            "user_proxy",
            "cbguder@a.co"
        ],
        [
            src_path("bin", "grouper-fe"),
            "-c",
            config_path
        ]
    ]

    subprocesses = []

    for cmd in cmds:
        p = subprocess.Popen(cmd)
        subprocesses.append(p)

    yield "http://localhost:8888"

    for p in subprocesses:
        p.kill()


@pytest.yield_fixture
def browser():
    options = webdriver.ChromeOptions()
    options.add_argument("headless")
    options.add_argument("window-size=1920,1080")

    driver = webdriver.Chrome(chrome_options=options)

    yield driver

    driver.quit()


def _write_test_config(tmpdir):
    with open(src_path("config", "dev.yaml")) as config_file:
        config = yaml.safe_load(config_file.read())

    config["common"]["database"] = db_url(tmpdir)
    config["common"]["plugin_dir"] = src_path("plugins")

    config_path = str(tmpdir.join("grouper.yaml"))
    with open(config_path, "w") as config_file:
        yaml.safe_dump(config, config_file)

    return config_path
