import pytest

from grouper import models
from grouper.models import get_db_engine, User, Group, Permission, Session
from grouper.graph import GroupGraph

from util import add_member


@pytest.fixture
def standard_graph(session, graph, users, groups):
    add_member(groups["team-sre"], users["gary"], role="owner")
    add_member(groups["team-sre"], users["zay"])
    add_member(groups["team-sre"], users["zorkian"])

    add_member(groups["tech-ops"], users["zay"], role="owner")
    add_member(groups["tech-ops"], users["gary"])

    add_member(groups["team-infra"], users["gary"], role="owner")
    add_member(groups["team-infra"], groups["team-sre"])
    add_member(groups["team-infra"], groups["tech-ops"])

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
        #models.Model.metadata.drop_all(db_engine)
    request.addfinalizer(fin)

    return session


@pytest.fixture
def graph(session):
    return GroupGraph.from_db(session)


@pytest.fixture
def users(session):
    users = {
        username: User.get_or_create(session, username=username)[0]
        for username in ("gary", "zay", "zorkian", "testuser")
    }
    session.commit()
    return users


@pytest.fixture
def groups(session):
    groups = {
        groupname: Group.get_or_create(session, groupname=groupname)[0]
        for groupname in ("team-sre", "tech-ops", "team-infra", "all-teams")
    }
    session.commit()
    return groups


@pytest.fixture
def permissions(session):
    permissions = {
        permission: Permission.get_or_create(
            session, name=permission, description="{} permission".format(permission))[0]
        for permission in ("ssh", "sudo")
    }
    session.commit()
    return permissions
