from typing import TYPE_CHECKING

from ctl_util import CtlTestRunner
from fixtures import (  # noqa: F401
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from grouper.permissions import get_permission

if TYPE_CHECKING:
    from grouper.graph import GroupGraph  # noqa: F401
    from grouper.models.base.session import Session  # noqa: F401


def test_permission_disable(session, standard_graph):  # noqa: F811
    # type: (Session, GroupGraph) -> None
    runner = CtlTestRunner(session)
    runner.run("permission", "-a", "gary@a.co", "disable", "audited")
    audited_permission = get_permission(session, "audited")
    assert not audited_permission.enabled
