from datetime import datetime, timedelta

from mock import patch
import pytest

from fixtures import groups, session, users  # noqa
from grouper.plugin import PluginRejectedGroupMembershipUpdate, PluginRejectedDisablingUser
from grouper.user import disable_user
from plugins.group_ownership_policy import GroupOwnershipPolicyPlugin
from util import add_member, revoke_member


@patch("grouper.group_member.get_plugins")
def test_cant_revoke_last_owner(get_plugins, session, groups, users):
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    group = groups["team-infra"]
    first_owner = users["gary@a.co"]
    second_owner = users["zay@a.co"]

    add_member(group, first_owner, role="owner")
    add_member(group, second_owner, role="owner")

    assert len(group.my_owners()) == 2

    # Revoking the first owner does not raise an exception
    revoke_member(group, first_owner)

    session.commit()
    assert len(group.my_owners()) == 1

    with pytest.raises(PluginRejectedGroupMembershipUpdate):
        revoke_member(group, second_owner)

    assert len(group.my_owners()) == 1


@patch("grouper.group_member.get_plugins")
def test_cant_revoke_last_npowner(get_plugins, session, groups, users):
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    group = groups["team-infra"]
    first_owner = users["gary@a.co"]
    second_owner = users["zay@a.co"]

    add_member(group, first_owner, role="np-owner")
    add_member(group, second_owner, role="np-owner")

    # Revoking the first owner does not raise an exception
    revoke_member(group, first_owner)

    session.commit()

    with pytest.raises(PluginRejectedGroupMembershipUpdate):
        revoke_member(group, second_owner)


@patch("grouper.group_member.get_plugins")
def test_cant_revoke_last_permanent_owner(get_plugins, groups, users):
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    group = groups["team-infra"]
    first_owner = users["gary@a.co"]
    second_owner = users["zay@a.co"]

    expiration = datetime.utcnow() + timedelta(1)

    add_member(group, first_owner, role="owner", expiration=expiration)
    add_member(group, second_owner, role="owner")

    with pytest.raises(PluginRejectedGroupMembershipUpdate):
        revoke_member(group, second_owner)


@patch("grouper.group_member.get_plugins")
def test_cant_expire_last_owner(get_plugins, groups, users):
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    group = groups["team-infra"]
    owner = users["gary@a.co"]

    expiration = datetime.utcnow() + timedelta(1)

    add_member(group, owner, role="owner")

    with pytest.raises(PluginRejectedGroupMembershipUpdate):
        group.edit_member(owner, owner, "Unit Testing", expiration=expiration)


@patch("grouper.group_member.get_plugins")
def test_cant_demote_last_owner(get_plugins, groups, users):
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    group = groups["team-infra"]
    owner = users["gary@a.co"]

    add_member(group, owner, role="owner")

    with pytest.raises(PluginRejectedGroupMembershipUpdate):
        group.edit_member(owner, owner, "Unit Testing", role="member")


@patch("grouper.group_member.get_plugins")
def test_can_always_revoke_members(get_plugins, groups, users):
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    group = groups["team-infra"]
    owner = users["gary@a.co"]
    member = users["zay@a.co"]

    expiration = datetime.utcnow() + timedelta(1)

    add_member(group, owner, role="owner", expiration=expiration)
    add_member(group, member)

    revoke_member(group, member)


@patch("grouper.user.get_plugins")
def test_cant_disable_last_owner(get_plugins, session, groups, users):
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    group = groups["team-infra"]
    owner = users["gary@a.co"]

    add_member(group, owner, role="owner")

    with pytest.raises(PluginRejectedDisablingUser):
        disable_user(session, owner)


@patch("grouper.user.get_plugins")
def test_can_disable_member(get_plugins, session, groups, users):
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    group = groups["team-infra"]
    member = users["gary@a.co"]

    add_member(group, member)
    disable_user(session, member)
