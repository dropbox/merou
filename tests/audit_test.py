from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import pytest
from mock import call, Mock, patch
from tornado.httpclient import HTTPError

from grouper.audit import (
    assert_can_join,
    assert_controllers_are_auditors,
    get_auditors_group,
    get_audits,
    get_group_audit_members_infos,
    GroupDoesNotHaveAuditPermission,
    user_is_auditor,
    UserNotAuditor,
)
from grouper.background.background_processor import BackgroundProcessor
from grouper.background.settings import BackgroundSettings
from grouper.constants import AUDIT_VIEWER, PERMISSION_AUDITOR
from grouper.graph import NoSuchGroup
from grouper.models.audit_log import AuditLog, AuditLogCategory
from grouper.models.group import Group
from grouper.models.permission_map import PermissionMap
from grouper.models.user import User
from grouper.permissions import enable_permission_auditing, get_or_create_permission
from grouper.settings import set_global_settings
from tests.fixtures import (  # noqa: F401
    fe_app as app,
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.url_util import url
from tests.util import add_member, get_users, grant_permission

if TYPE_CHECKING:
    from typing import List


def test_group_audited(standard_graph, graph, session, groups, permissions):  # noqa: F811
    """Ensure that the audited flag gets set appropriate only groups and inherited down the
    graph."""
    assert not graph.get_group_details("security-team")["audited"]
    assert graph.get_group_details("serving-team")["audited"]
    assert graph.get_group_details("team-sre")["audited"]


def test_user_is_auditor(standard_graph):  # noqa: F811
    """Ensure users get the ability to audit."""

    assert user_is_auditor("zorkian@a.co")
    assert not user_is_auditor("oliver@a.co")


def test_assert_can_join(standard_graph, users, groups):  # noqa: F811
    """Test various audit constraints to ensure that users can/can't join as appropriate."""

    # Non-auditor can join non-audited group as owner.
    assert_can_join(groups["team-infra"], users["zay@a.co"], role="owner")

    # Auditor can join non-audited group as owner.
    assert_can_join(groups["team-infra"], users["zorkian@a.co"], role="owner")

    # Non-auditor can NOT join audited group as owner.
    with pytest.raises(UserNotAuditor):
        assert_can_join(groups["serving-team"], users["zay@a.co"], role="owner")

    # Non-auditor can join audited group as member.
    assert_can_join(groups["serving-team"], users["zay@a.co"])

    # Group with non-auditor owner can NOT join audited group.
    with pytest.raises(UserNotAuditor):
        assert_can_join(groups["serving-team"], groups["tech-ops"])

    # Group with auditor owner can join audited group.
    assert_can_join(groups["serving-team"], groups["sad-team"])

    # Group with non-auditor owner can join non-audited group.
    assert_can_join(groups["team-infra"], groups["tech-ops"])

    # Group with auditor owner, but sub-group with non-auditor owner, can NOT join audited group.
    with pytest.raises(UserNotAuditor):
        assert_can_join(groups["audited-team"], groups["serving-team"])


def test_assert_controllers_are_auditors(standard_graph, groups):  # noqa: F811
    """Test the method that determines if a subtree is controlled by auditors."""

    # Group is safely controlled by auditors.
    assert_controllers_are_auditors(groups["sad-team"])

    # Group with non-auditor owner should fail this test.
    with pytest.raises(UserNotAuditor):
        assert_controllers_are_auditors(groups["team-infra"])


@pytest.mark.gen_test
def test_toggle_perm_audited(groups, permissions, http_client, base_url):  # noqa: F811
    perm_name = "audited"  # perm that is already audited
    nonpriv_user_name = "oliver@a.co"  # user with no audit perms and without PERMISSION_ADMIN
    nonpriv_user_team = "sad-team"
    nonpriv_headers = {"X-Grouper-User": nonpriv_user_name}
    priv_user_name = "zorkian@a.co"  # user with AUDIT_MANAGER
    priv_headers = {"X-Grouper-User": priv_user_name}
    enable_url = url(base_url, "/permissions/{}/enable-auditing".format(perm_name))
    disable_url = url(base_url, "/permissions/{}/disable-auditing".format(perm_name))

    # Give nonpriv user audit view permissions, which shouldn't allow enabling/disabling auditing
    grant_permission(groups[nonpriv_user_team], permissions[AUDIT_VIEWER], argument="")

    # attempt to enable/disable auditing; both should fail due to lack of perms
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(enable_url, method="POST", headers=nonpriv_headers, body="")
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(
            disable_url, method="POST", headers=nonpriv_headers, body=""
        )

    # Now confirm that enabling/disabling auditing works as a privileged user
    # Note that enabling audits on an audited perm succeeds (same for disabling)
    resp = yield http_client.fetch(enable_url, method="POST", headers=priv_headers, body="")
    assert resp.code == 200
    # Perm is still audited
    resp = yield http_client.fetch(disable_url, method="POST", headers=priv_headers, body="")
    assert resp.code == 200
    # Perm no longer audited
    resp = yield http_client.fetch(disable_url, method="POST", headers=priv_headers, body="")
    assert resp.code == 200
    # Perm still not audited
    resp = yield http_client.fetch(enable_url, method="POST", headers=priv_headers, body="")
    assert resp.code == 200
    # Perm audited again


@dataclass(frozen=True)
class MyAuditMemberInfo:
    am_id: int
    edge_type: int
    edge_id: int


@dataclass(frozen=True)
class Audit:
    audit_id: int
    owner_name: str
    group_name: str
    audit_members_infos: List[MyAuditMemberInfo]


@pytest.mark.gen_test
def test_audit_end_to_end(session, users, groups, http_client, base_url, graph):  # noqa: F811
    """Tests an end-to-end audit cycle."""
    groupname = "audited-team"

    gary_id = users["gary@a.co"].id

    # make everyone an auditor or global audit will have issues
    add_member(groups["auditors"], users["gary@a.co"])
    add_member(groups["auditors"], users["oliver@a.co"])
    add_member(groups["auditors"], users["zay@a.co"])
    add_member(groups["auditors"], users["figurehead@a.co"])

    # add some users to test removal
    add_member(groups[groupname], users["zay@a.co"])
    add_member(groups[groupname], users["gary@a.co"])

    graph.update_from_db(session)

    # start the audit
    end_at_str = (datetime.now() + timedelta(days=10)).strftime("%m/%d/%Y")
    fe_url = url(base_url, "/audits/create")
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"ends_at": end_at_str}),
        headers={"X-Grouper-User": "zorkian@a.co"},
    )
    assert resp.code == 200

    open_audits = get_audits(session, only_open=True).all()
    assert len(open_audits) == 4, "audits created"

    assert groupname in [x.group.name for x in open_audits], "group we expect also gets audit"

    # pull all the info we need to resolve audits, avoids detached sqlalchemy sessions
    # (DetachedInstanceError)
    all_group_ids = [x.group.id for x in open_audits]
    open_audits = [
        Audit(
            x.id,
            next(iter(x.group.my_owners())),
            x.group.name,
            [
                MyAuditMemberInfo(
                    ami.audit_member_obj.id,
                    ami.audit_member_obj.edge.member_type,
                    ami.audit_member_obj.edge_id,
                )
                for ami in get_group_audit_members_infos(session, x.group)
            ],
        )
        for x in open_audits
    ]

    # approve everything but the one we added members to
    for one_audit in open_audits:
        fe_url = url(base_url, "/audits/{}/complete".format(one_audit.audit_id))

        if one_audit.group_name == groupname:
            continue

        # blanket approval
        body = urlencode(
            {"audit_{}".format(ami.am_id): "approved" for ami in one_audit.audit_members_infos}
        )

        resp = yield http_client.fetch(
            fe_url, method="POST", body=body, headers={"X-Grouper-User": one_audit.owner_name}
        )
        assert resp.code == 200

    open_audits = get_audits(session, only_open=True).all()
    assert len(open_audits) == 1, "only our test group remaining"

    one_audit = open_audits[0]
    one_audit.id

    body_dict = {}
    for ami in get_group_audit_members_infos(session, one_audit.group):
        if gary_id == ami.member_obj.id:
            # deny
            body_dict["audit_{}".format(ami.audit_member_obj.id)] = "remove"
        else:
            # approve
            body_dict["audit_{}".format(ami.audit_member_obj.id)] = "approved"

    owner_name = next(iter(one_audit.group.my_owners()))
    fe_url = url(base_url, "/audits/{}/complete".format(one_audit.id))
    resp = yield http_client.fetch(
        fe_url, method="POST", body=urlencode(body_dict), headers={"X-Grouper-User": owner_name}
    )
    assert resp.code == 200

    # check all the logs
    assert len(AuditLog.get_entries(session, action="start_audit")) == 1, "global start is logged"
    assert (
        len(AuditLog.get_entries(session, action="complete_global_audit")) == 1
    ), "global complete is logged"

    for group_id in all_group_ids:
        assert (
            len(
                AuditLog.get_entries(
                    session,
                    on_group_id=group_id,
                    action="complete_audit",
                    category=AuditLogCategory.audit,
                )
            )
            == 1
        ), "complete entry for each group"

    assert (
        len(AuditLog.get_entries(session, on_user_id=gary_id, category=AuditLogCategory.audit))
        == 1
    ), "removal AuditLog entry on user"


@patch("grouper.audit.get_auditors_group_name")
@patch("grouper.background.background_processor.notify_nonauditor_promoted")
def test_auditor_promotion(mock_nnp, mock_gagn, session, graph, permissions, users):  # noqa: F811
    """Test automatic promotion of non-auditor approvers

    We set up our own group/user/permission for testing instead of
    using the `standard_graph` fixture---retrofitting it to work for
    us and also not break existing tests is too cumbersome.

    So here are our groups:

    very-special-auditors:
      * user14

    group-1:
      * user11 (o)
      * user12
      * user13 (np-o)
      * user14 (o, a)

    group-2:
      * user13 (np-o)
      * user21 (o)
      * user22

    group-3:
      * user22 (o)
      * user12 (o)

    group-4:
      * user21 (np-o)
      * user41
      * user42 (o)
      * user43 (np-o)

    o: owner, np-o: no-permission owner, a: auditor

    group-1 and group-2 have the permission that we will enable
    auditing. group-4 will be a subgroup of group-1 and thus will
    inherit the audited permission from group-1.

    The expected outcome is: user11, user13, user21, user42, and
    user43 will be added to the auditors group.

    """
    settings = BackgroundSettings()
    set_global_settings(settings)

    #
    # set up our test part of the graph
    #

    # create groups
    AUDITED_GROUP = "audited"
    AUDITORS_GROUP = mock_gagn.return_value = "very-special-auditors"
    PERMISSION_NAME = "test-permission"
    all_groups = {
        groupname: Group.get_or_create(session, groupname=groupname)[0]
        for groupname in ("group-1", "group-2", "group-3", "group-4", AUDITORS_GROUP)
    }
    # create users
    users.update(
        {
            username + "@a.co": User.get_or_create(session, username=username + "@a.co")[0]
            for username in (
                "user11",
                "user12",
                "user13",
                "user14",
                "user21",
                "user22",
                "user23",
                "user41",
                "user42",
                "user43",
            )
        }
    )
    # create permissions
    permissions.update(
        {
            permission: get_or_create_permission(
                session, permission, description="{} permission".format(permission)
            )[0]
            for permission in [PERMISSION_NAME]
        }
    )
    # add users to groups
    for (groupname, username, role) in (
        ("group-1", "user11", "owner"),
        ("group-1", "user12", "member"),
        ("group-1", "user13", "np-owner"),
        ("group-1", "user14", "owner"),
        ("group-2", "user13", "np-owner"),
        ("group-2", "user21", "owner"),
        ("group-2", "user22", "member"),
        ("group-3", "user12", "owner"),
        ("group-3", "user22", "owner"),
        ("group-4", "user21", "np-owner"),
        ("group-4", "user41", "member"),
        ("group-4", "user42", "owner"),
        ("group-4", "user43", "np-owner"),
    ):
        add_member(all_groups[groupname], users[username + "@a.co"], role=role)
    # add group-4 as member of group-1
    add_member(all_groups["group-1"], all_groups["group-4"])
    # add user14 to auditors group
    add_member(all_groups[AUDITORS_GROUP], users["user14@a.co"])
    # grant permissions to groups
    #
    # give the test permission to groups 1 and 2, and group 4 should
    # also inherit from group 1
    grant_permission(all_groups["group-1"], permissions[PERMISSION_NAME])
    grant_permission(all_groups["group-2"], permissions[PERMISSION_NAME])
    grant_permission(all_groups[AUDITORS_GROUP], permissions[PERMISSION_AUDITOR])

    graph.update_from_db(session)
    # done setting up

    # now a few pre-op checks
    assert not graph.get_group_details("group-1").get(AUDITED_GROUP)
    assert not graph.get_group_details("group-4").get(AUDITED_GROUP)
    assert get_users(graph, AUDITORS_GROUP) == set(["user14@a.co"])
    assert get_users(graph, "group-3") == set(["user12@a.co", "user22@a.co"])

    #
    # run the promotion logic -> nothing should happen because the
    # test-permission is not yet audited
    #
    background = BackgroundProcessor(settings, None)
    background.promote_nonauditors(session)
    graph.update_from_db(session)

    # nothing should have happened
    assert not graph.get_group_details("group-1").get(AUDITED_GROUP)
    assert not graph.get_group_details("group-4").get(AUDITED_GROUP)
    assert get_users(graph, AUDITORS_GROUP) == set(["user14@a.co"])
    assert mock_nnp.call_count == 0

    #
    # now enable auditing for the permission and run the promotion
    # logic again
    #
    enable_permission_auditing(session, PERMISSION_NAME, users["zorkian@a.co"].id)
    graph.update_from_db(session)
    assert graph.get_group_details("group-1").get(AUDITED_GROUP)
    assert graph.get_group_details("group-4").get(AUDITED_GROUP)

    background = BackgroundProcessor(settings, None)
    background.promote_nonauditors(session)
    graph.update_from_db(session)

    # check that stuff happened
    assert get_users(graph, AUDITORS_GROUP) == set(
        ["user11@a.co", "user13@a.co", "user14@a.co", "user21@a.co", "user42@a.co", "user43@a.co"]
    )
    expected_calls = [
        call(
            settings, session, users["user11@a.co"], all_groups[AUDITORS_GROUP], set(["group-1"])
        ),
        call(
            settings,
            session,
            users["user13@a.co"],
            all_groups[AUDITORS_GROUP],
            set(["group-1", "group-2"]),
        ),
        call(
            settings,
            session,
            users["user21@a.co"],
            all_groups[AUDITORS_GROUP],
            set(["group-2", "group-4"]),
        ),
        call(
            settings, session, users["user42@a.co"], all_groups[AUDITORS_GROUP], set(["group-4"])
        ),
        call(
            settings, session, users["user43@a.co"], all_groups[AUDITORS_GROUP], set(["group-4"])
        ),
    ]
    assert mock_nnp.call_count == len(expected_calls)
    mock_nnp.assert_has_calls(expected_calls, any_order=True)

    #
    # run the background promotion logic again, and nothing should
    # happen
    #
    mock_nnp.reset_mock()
    background = BackgroundProcessor(settings, None)
    background.promote_nonauditors(session)
    assert mock_nnp.call_count == 0


def test_get_auditors_group(session, standard_graph):  # noqa: F811
    with pytest.raises(NoSuchGroup) as exc:
        get_auditors_group(Mock(auditors_group=None), session)
    assert str(exc.value) == "Please ask your admin to configure the `auditors_group` settings"
    with pytest.raises(NoSuchGroup) as exc:
        get_auditors_group(Mock(auditors_group="do-not-exist"), session)
    assert str(exc.value) == "Please ask your admin to configure the default group for auditors"
    # now should be able to get the group
    auditors_group = get_auditors_group(Mock(auditors_group="auditors"), session)
    assert auditors_group is not None
    # revoke the permission and make sure we raise the
    # GroupDoesNotHaveAuditPermission exception
    perms = [p for p in auditors_group.my_permissions() if p.name == PERMISSION_AUDITOR]
    assert len(perms) == 1
    mapping = PermissionMap.get(session, id=perms[0].mapping_id)
    mapping.delete(session)
    with pytest.raises(GroupDoesNotHaveAuditPermission):
        get_auditors_group(Mock(auditors_group="auditors"), session)
