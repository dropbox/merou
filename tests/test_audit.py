import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa

from grouper.audit import (
    assert_controllers_are_auditors, assert_can_join, user_is_auditor, UserNotAuditor
)


def test_group_audited(standard_graph, session, groups, permissions):  # noqa
    """ Ensure that the audited flag gets set appropriate only groups and inherited down the
        graph. """

    graph = standard_graph  # noqa

    assert not graph.get_group_details("security-team")["audited"]
    assert graph.get_group_details("serving-team")["audited"]
    assert graph.get_group_details("team-sre")["audited"]


def test_user_is_auditor(standard_graph):  # noqa
    """ Ensure users get the ability to audit. """

    assert user_is_auditor("zorkian")
    assert not user_is_auditor("oliver")


def test_assert_can_join(users, groups):  # noqa
    """ Test various audit constraints to ensure that users can/can't join as appropriate. """

    # Non-auditor can join non-audited group as owner.
    assert assert_can_join(groups["team-infra"], users["zay"], role="owner")

    # Auditor can join non-audited group as owner.
    assert assert_can_join(groups["team-infra"], users["zorkian"], role="owner")

    # Non-auditor can NOT join audited group as owner.
    with pytest.raises(UserNotAuditor):
        assert not assert_can_join(groups["serving-team"], users["zay"], role="owner")

    # Non-auditor can join audited group as member.
    assert assert_can_join(groups["serving-team"], users["zay"])

    # Group with non-auditor owner can NOT join audited group.
    with pytest.raises(UserNotAuditor):
        assert not assert_can_join(groups["serving-team"], groups["tech-ops"])

    # Group with auditor owner can join audited group.
    assert assert_can_join(groups["serving-team"], groups["sad-team"])

    # Group with non-auditor owner can join non-audited group.
    assert assert_can_join(groups["team-infra"], groups["tech-ops"])

    # Group with auditor owner, but sub-group with non-auditor owner, can NOT join audited group.
    with pytest.raises(UserNotAuditor):
        assert not assert_can_join(groups["audited-team"], groups["serving-team"])


def test_assert_controllers_are_auditors(groups):  # noqa
    """ Test the method that determines if a subtree is controlled by auditors. """

    # Group is safely controlled by auditors.
    assert assert_controllers_are_auditors(groups["sad-team"])

    # Group with non-auditor owner should fail this test.
    with pytest.raises(UserNotAuditor):
        assert not assert_controllers_are_auditors(groups["team-infra"])
