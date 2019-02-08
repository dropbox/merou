from typing import TYPE_CHECKING

from grouper.permissions import get_permission
from tests.ctl_util import CtlTestRunner
from tests.fixtures import (  # noqa: F401
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session


def test_permission_disable(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    runner = CtlTestRunner(session)
    runner.run("permission", "-a", "gary@a.co", "disable", "audited")
    audited_permission = get_permission(session, "audited")
    assert audited_permission
    assert not audited_permission.enabled
