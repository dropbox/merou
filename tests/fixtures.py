import pytest

from grouper import models
from grouper.models import get_db_engine, User, Group, Permission, Session
from grouper.graph import GroupGraph


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
    users = {}
    users["gary"] = User.get_or_create(session, username="gary")[0]
    users["zay"] = User.get_or_create(session, username="zay")[0]
    users["zorkian"] = User.get_or_create(session, username="zorkian")[0]
    users["testuser"] = User.get_or_create(session, username="testuser")[0]
    session.commit()
    return users


@pytest.fixture
def groups(session):
    groups = {}
    groups["team-sre"] = Group.get_or_create(session, groupname="team-sre")[0]
    groups["tech-ops"] = Group.get_or_create(session, groupname="tech-ops")[0]
    groups["team-infra"] = Group.get_or_create(session, groupname="team-infra")[0]
    groups["all-teams"] = Group.get_or_create(session, groupname="all-teams")[0]
    session.commit()
    return groups


@pytest.fixture
def permissions(session):
    permissions = {}
    permissions["ssh"] = Permission.get_or_create(
        session, name="ssh", description="ssh permission")[0]
    permissions["sudo"] = Permission.get_or_create(
        session, name="sudo", description="sudo permission")[0]
    session.commit()
    return permissions
