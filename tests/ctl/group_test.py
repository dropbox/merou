import csv
from datetime import date, timedelta

from mock import patch

from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.plugin.proxy import PluginProxy
from plugins.group_ownership_policy import GroupOwnershipPolicyPlugin
from tests.ctl_util import call_main
from tests.fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401


def test_group_add_remove_member(session, tmpdir, users, groups):  # noqa: F811
    username = "oliver@a.co"
    groupname = "team-sre"

    # add
    assert ("User", username) not in groups[groupname].my_members()
    call_main(session, tmpdir, "group", "add_member", "--member", groupname, username)
    all_members = Group.get(session, name=groupname).my_members()
    assert ("User", username) in all_members
    _, _, _, role, _, _ = all_members[("User", username)]
    assert GROUP_EDGE_ROLES[role] == "member"

    # remove
    call_main(session, tmpdir, "group", "remove_member", groupname, username)
    assert ("User", username) not in Group.get(session, name=groupname).my_members()


@patch("grouper.group_member.get_plugin_proxy")
def test_group_add_remove_owner(get_plugin_proxy, session, tmpdir, users, groups):  # noqa: F811
    get_plugin_proxy.return_value = PluginProxy([GroupOwnershipPolicyPlugin()])

    username = "oliver@a.co"
    groupname = "team-sre"

    # add
    assert ("User", username) not in groups[groupname].my_members()
    call_main(session, tmpdir, "group", "add_member", "--owner", groupname, username)
    all_members = Group.get(session, name=groupname).my_members()
    assert ("User", username) in all_members
    _, _, _, role, _, _ = all_members[("User", username)]
    assert GROUP_EDGE_ROLES[role] == "owner"

    # remove (fails)
    call_main(session, tmpdir, "group", "remove_member", groupname, username)
    assert ("User", username) in Group.get(session, name=groupname).my_members()


def test_group_bulk_add_remove(session, tmpdir, users, groups):  # noqa: F811
    groupname = "team-sre"

    # bulk add
    usernames = {"oliver@a.co", "testuser@a.co", "zebu@a.co"}
    call_main(session, tmpdir, "group", "add_member", "--member", groupname, *usernames)
    members = {u for _, u in Group.get(session, name=groupname).my_members()}
    assert usernames.issubset(members)

    # bulk remove
    call_main(session, tmpdir, "group", "remove_member", groupname, *usernames)
    members = {u for _, u in Group.get(session, name=groupname).my_members()}
    assert not members.intersection(usernames)


def test_group_name_checks(session, tmpdir, users, groups):  # noqa: F811
    username = "oliver@a.co"
    groupname = "team-sre"

    # check user/group name
    call_main(session, tmpdir, "group", "add_member", "--member", "invalid group name", username)
    assert ("User", username) not in Group.get(session, name=groupname).my_members()

    bad_username = "not_a_valid_username"
    call_main(session, tmpdir, "group", "add_member", "--member", groupname, bad_username)
    assert ("User", bad_username) not in Group.get(session, name=groupname).my_members()


def test_group_logdump(session, tmpdir, users, groups):  # noqa: F811
    groupname = "team-sre"
    group_id = groups[groupname].id

    yesterday = date.today() - timedelta(days=1)
    fn = tmpdir.join("out.csv").strpath

    call_main(
        session, tmpdir, "group", "log_dump", groupname, yesterday.isoformat(), "--outfile", fn
    )
    with open(fn, "r") as fh:
        out = fh.read()

    assert not out, "nothing yet"

    AuditLog.log(
        session, users["zorkian@a.co"].id, "make_noise", "making some noise", on_group_id=group_id
    )
    session.commit()

    call_main(
        session, tmpdir, "group", "log_dump", groupname, yesterday.isoformat(), "--outfile", fn
    )
    with open(fn, "r") as fh:
        entries = [x for x in csv.reader(fh)]

    assert len(entries) == 1, "should capture our new audit log entry"

    log_time, actor, description, action, extra = entries[0]
    assert groupname in extra
