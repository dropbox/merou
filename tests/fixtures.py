import pytest

from grouper import models
from grouper.constants import PERMISSION_AUDITOR
from grouper.models import get_db_engine, User, Group, Permission, Session
from grouper.graph import Graph

from util import add_member, grant_permission


@pytest.fixture
def standard_graph(session, graph, users, groups, permissions):
    add_member(groups["team-sre"], users["gary"], role="owner")
    add_member(groups["team-sre"], users["zay"])
    add_member(groups["team-sre"], users["zorkian"])
    grant_permission(groups["team-sre"], permissions["ssh"], argument="*")

    add_member(groups["serving-team"], users["zorkian"], role="owner")
    add_member(groups["serving-team"], groups["team-sre"])
    add_member(groups["serving-team"], groups["tech-ops"])
    grant_permission(groups["serving-team"], permissions["audited"])

    add_member(groups["tech-ops"], users["zay"], role="owner")
    add_member(groups["tech-ops"], users["gary"])
    grant_permission(groups["tech-ops"], permissions["ssh"], argument="shell")

    add_member(groups["security-team"], users["oliver"], role="owner")

    add_member(groups["sad-team"], users["zorkian"], role="owner")
    add_member(groups["sad-team"], users["oliver"])

    add_member(groups["audited-team"], users["zorkian"], role="owner")
    grant_permission(groups["audited-team"], permissions["audited"])

    add_member(groups["team-infra"], users["gary"], role="owner")
    add_member(groups["team-infra"], groups["serving-team"])
    add_member(groups["team-infra"], groups["security-team"])
    grant_permission(groups["team-infra"], permissions["sudo"], argument="shell")

    add_member(groups["auditors"], users["zorkian"], role="owner")
    grant_permission(groups["auditors"], permissions[PERMISSION_AUDITOR])

    add_member(groups["all-teams"], users["testuser"], role="owner")
    add_member(groups["all-teams"], groups["team-infra"])

    session.commit()
    graph.update_from_db(session)

    return graph


@pytest.fixture
def session(request, tmpdir):
    db_path = tmpdir.join("grouper.sqlite")
    db_engine = get_db_engine("sqlite:///%s" % db_path)

    models.Model.metadata.create_all(db_engine)
    Session.configure(bind=db_engine)
    session = Session()

    def fin():
        session.close()
        # Useful if testing against MySQL
        # models.Model.metadata.drop_all(db_engine)
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
        for username in ("gary", "zay", "zorkian", "oliver", "testuser")
    }
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
def permissions(session):
    permissions = {
        permission: Permission.get_or_create(
            session, name=permission, description="{} permission".format(permission))[0]
        for permission in ("ssh", "sudo", "audited", PERMISSION_AUDITOR)
    }
    permissions["audited"].enable_auditing()
    session.commit()
    return permissions
