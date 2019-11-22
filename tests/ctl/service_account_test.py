from typing import TYPE_CHECKING

import pytest

from grouper.constants import USER_ADMIN
from grouper.group_service_account import get_service_accounts
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from tests.ctl_util import run_ctl

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_create(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.add_user_to_group("gary@a.co", "other-group")

    run_ctl(
        setup,
        "service_account",
        "--actor",
        "gary@a.co",
        "create",
        "good-service@svc.localhost",
        "some-group",
        "foo +bar -(org)",
        "this is a service account.\n\n it is for testing",
    )
    service_account = ServiceAccount.get(setup.session, name="good-service@svc.localhost")
    assert service_account is not None
    assert service_account.user.name == "good-service@svc.localhost"
    assert service_account.machine_set == "foo +bar -(org)"
    assert service_account.description == "this is a service account.\n\n it is for testing"
    group = Group.get(setup.session, name="some-group")
    assert group
    assert get_service_accounts(setup.session, group) == [service_account]

    # If the account already exists, creating it again returns an error and does nothing.
    with pytest.raises(SystemExit):
        run_ctl(
            setup,
            "service_account",
            "--actor",
            "gary@a.co",
            "create",
            "good-service@svc.localhost",
            "other-group",
            "foo",
            "another test",
        )
    service_account = ServiceAccount.get(setup.session, name="good-service@svc.localhost")
    assert service_account is not None
    assert service_account.machine_set == "foo +bar -(org)"
    assert service_account.description == "this is a service account.\n\n it is for testing"
    group = Group.get(setup.session, name="some-group")
    assert group
    assert get_service_accounts(setup.session, group) == [service_account]


def test_create_as_service_account(setup):
    """Test that a service account can create another service account."""
    with setup.transaction():
        setup.create_group("some-group")
        setup.create_service_account("creator@a.co", "another-group")
        setup.grant_permission_to_service_account(USER_ADMIN, "", "creator@a.co")

    run_ctl(
        setup,
        "service_account",
        "--actor",
        "creator@a.co",
        "create",
        "good-service@svc.localhost",
        "some-group",
        "foo +bar -(org)",
        "this is a service account.\n\n it is for testing",
    )
    service_account = ServiceAccount.get(setup.session, name="good-service@svc.localhost")
    assert service_account is not None
    assert service_account.user.name == "good-service@svc.localhost"
    assert service_account.machine_set == "foo +bar -(org)"
    assert service_account.description == "this is a service account.\n\n it is for testing"
    group = Group.get(setup.session, name="some-group")
    assert get_service_accounts(setup.session, group) == [service_account]


def test_create_invalid_actor(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_group("some-group")

    with pytest.raises(SystemExit):
        run_ctl(
            setup,
            "service_account",
            "--actor",
            "gary@a.co",
            "create",
            "good-service@svc.localhost",
            "some-group",
            "foo",
            "another test",
        )

    assert ServiceAccount.get(setup.session, name="good-service@a.co") is None
    group = Group.get(setup.session, name="some-group")
    assert group
    assert get_service_accounts(setup.session, group) == []


def test_create_bad_name(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    with pytest.raises(SystemExit):
        run_ctl(
            setup,
            "service_account",
            "--actor",
            "gary@a.co",
            "create",
            "good-service@a.co",
            "some-group",
            "foo",
            "another test",
        )

    assert ServiceAccount.get(setup.session, name="good-service@a.co") is None
    group = Group.get(setup.session, name="some-group")
    assert group
    assert get_service_accounts(setup.session, group) == []


def test_create_bad_owner(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    with pytest.raises(SystemExit):
        run_ctl(
            setup,
            "service_account",
            "--actor",
            "gary@a.co",
            "create",
            "good-service@svc.localhost",
            "nonexistent-group",
            "foo",
            "another test",
        )

    assert ServiceAccount.get(setup.session, name="good-service@svc.localhost") is None
    group = Group.get(setup.session, name="some-group")
    assert group
    assert get_service_accounts(setup.session, group) == []
    assert Group.get(setup.session, name="nonexistent-group") is None
