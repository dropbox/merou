from typing import TYPE_CHECKING

from mock import call, MagicMock

from grouper.constants import MAX_NAME_LENGTH, SERVICE_ACCOUNT_VALIDATION, USER_ADMIN
from grouper.models.group import Group
from grouper.models.group_service_accounts import GroupServiceAccount
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User
from grouper.plugin.base import BasePlugin
from grouper.plugin.exceptions import PluginRejectedMachineSet, PluginRejectedServiceAccountName
from grouper.user_metadata import get_user_metadata

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_can_create(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.create_group("another-group")
        setup.add_user_to_group("zorkian@a.co", "admins")
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")
        setup.create_service_account("service@a.co", "some-group")
        setup.create_service_account("admin@a.co", "some-group")
        setup.grant_permission_to_service_account(USER_ADMIN, "", "admin@a.co")

    mock_ui = MagicMock()

    # Regular group member.
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    assert usecase.can_create_service_account("some-group")
    assert not usecase.can_create_service_account("another-group")

    # Admin.
    usecase = setup.usecase_factory.create_create_service_account_usecase("zorkian@a.co", mock_ui)
    assert usecase.can_create_service_account("some-group")
    assert usecase.can_create_service_account("another-group")

    # Service account admin.
    usecase = setup.usecase_factory.create_create_service_account_usecase("admin@a.co", mock_ui)
    assert usecase.can_create_service_account("some-group")
    assert usecase.can_create_service_account("another-group")

    # Service account with no special permissions.
    usecase = setup.usecase_factory.create_create_service_account_usecase("service@a.co", mock_ui)
    assert not usecase.can_create_service_account("some-group")
    assert not usecase.can_create_service_account("another-group")


def test_success(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account(
        "service@svc.localhost", "some-group", "machine-set", "description"
    )
    assert mock_ui.mock_calls == [
        call.created_service_account("service@svc.localhost", "some-group")
    ]

    # Check the User and ServiceAccount that were created.
    user = User.get(setup.session, name="service@svc.localhost")
    assert user is not None
    assert user.is_service_account
    assert user.enabled
    service = ServiceAccount.get(setup.session, name="service@svc.localhost")
    assert service is not None
    assert service.machine_set == "machine-set"
    assert service.description == "description"

    # Check that the ServiceAccount is owned by the correct Group.
    group = Group.get(setup.session, name="some-group")
    assert group is not None
    linkage = GroupServiceAccount.get(setup.session, service_account_id=service.id)
    assert linkage is not None
    assert linkage.group_id == group.id

    # Check that the user appears in the graph.
    setup.graph.update_from_db(setup.session)
    metadata = setup.graph.user_metadata["service@svc.localhost"]
    assert metadata["enabled"]
    assert metadata["service_account"]["description"] == "description"
    assert metadata["service_account"]["machine_set"] == "machine-set"
    assert metadata["service_account"]["owner"] == "some-group"
    group_details = setup.graph.get_group_details("some-group")
    assert group_details["service_accounts"] == ["service@svc.localhost"]


def test_success_set_initial_metadata(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    initial_metadata = {"test-item-1": "foo", "test-item-2": "bar"}

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account(
        "service@svc.localhost", "some-group", "machine-set", "description", initial_metadata
    )

    user = User.get(setup.session, name="service@svc.localhost")
    assert user is not None
    metadata_items = get_user_metadata(setup.session, user.id)
    actual_items = {mi.data_key: mi.data_value for mi in metadata_items}
    assert len(initial_metadata) == len(actual_items)
    for key, value in initial_metadata.items():
        assert key in actual_items
        assert initial_metadata[key] == actual_items[key]

    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account(
        "another_service@svc.localhost", "some-group", "machine-set", "description"
    )
    user = User.get(setup.session, name="another_service@svc.localhost")
    assert user is not None
    metadata_items = get_user_metadata(setup.session, user.id)
    assert metadata_items == []


def test_add_domain(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account("service", "some-group", "machine-set", "description")

    service = ServiceAccount.get(setup.session, name="service@svc.localhost")
    assert service is not None
    assert service.machine_set == "machine-set"
    assert service.description == "description"
    assert ServiceAccount.get(setup.session, name="service") is None


def test_admin_can_create(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_group("some-group")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account("service@svc.localhost", "some-group", "", "")
    assert mock_ui.mock_calls == [
        call.created_service_account("service@svc.localhost", "some-group")
    ]

    service = ServiceAccount.get(setup.session, name="service@svc.localhost")
    assert service is not None
    assert service.machine_set == ""
    assert service.description == ""


def test_permission_denied(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_group("some-group")
        setup.create_user("gary@a.co")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account("service@svc.localhost", "some-group", "", "")
    assert mock_ui.mock_calls == [
        call.create_service_account_failed_permission_denied("service@svc.localhost", "some-group")
    ]


def test_invalid_name(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account("service@foo@bar", "some-group", "", "")
    assert mock_ui.mock_calls == [
        call.create_service_account_failed_invalid_name(
            "service@foo@bar",
            "some-group",
            "service@foo@bar is not a valid service account name (does not match {})".format(
                SERVICE_ACCOUNT_VALIDATION
            ),
        )
    ]

    # Test a service account name that's one character longer than MAX_NAME_LENGTH minus the length
    # of the default email domain minus 1 (for the @).
    mock_ui.reset_mock()
    long_name = "x" * (MAX_NAME_LENGTH - len(setup.settings.service_account_email_domain))
    long_name += "@" + setup.settings.service_account_email_domain
    usecase.create_service_account(long_name, "some-group", "", "")
    assert mock_ui.mock_calls == [
        call.create_service_account_failed_invalid_name(
            long_name,
            "some-group",
            "{} is longer than {} characters".format(long_name, MAX_NAME_LENGTH),
        )
    ]

    mock_ui.reset_mock()
    usecase.create_service_account("service@a.co", "some-group", "", "")
    assert mock_ui.mock_calls == [
        call.create_service_account_failed_invalid_name(
            "service@a.co",
            "some-group",
            "All service accounts must end in @{}".format(
                setup.settings.service_account_email_domain
            ),
        )
    ]


def test_invalid_owner(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account("service@svc.localhost", "some-group", "", "")
    assert mock_ui.mock_calls == [
        call.create_service_account_failed_invalid_owner("service@svc.localhost", "some-group")
    ]


class MachineSetTestPlugin(BasePlugin):
    def check_machine_set(self, name, machine_set):
        # type: (str, str) -> None
        assert name == "service@svc.localhost"
        raise PluginRejectedMachineSet("some error message")


def test_invalid_machine_set(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    setup.plugins.add_plugin(MachineSetTestPlugin())

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account("service@svc.localhost", "some-group", "machine-set", "")
    assert mock_ui.mock_calls == [
        call.create_service_account_failed_invalid_machine_set(
            "service@svc.localhost", "some-group", "machine-set", "some error message"
        )
    ]


class ServiceAccountNameTestPlugin(BasePlugin):
    def check_service_account_name(self, name):
        # type: (str) -> None
        if "_" in name:
            raise PluginRejectedServiceAccountName(name)


def test_name_rejected_by_plugin(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    setup.plugins.add_plugin(ServiceAccountNameTestPlugin())

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", mock_ui)
    usecase.create_service_account("ser_vice", "some-group", "", "")
    assert mock_ui.mock_calls == [
        call.create_service_account_failed_invalid_name(
            "ser_vice@svc.localhost", "some-group", "ser_vice@svc.localhost"
        )
    ]

    mock_ui.reset_mock()
    usecase.create_service_account("service", "some-group", "", "")
    assert mock_ui.mock_calls == [
        call.created_service_account("service@svc.localhost", "some-group")
    ]


class ServiceAccountCreatedPlugin(BasePlugin):
    def user_created(self, user, is_service_account=False):
        # type: (User, bool) -> None
        assert is_service_account and user.is_service_account
        assert user.id
        assert user.enabled
        assert not user.role_user


def test_user_created_plugin_invocation(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    setup.plugins.add_plugin(ServiceAccountCreatedPlugin())

    ui = MagicMock()
    usecase = setup.usecase_factory.create_create_service_account_usecase("gary@a.co", ui)
    usecase.create_service_account("service", "some-group", "", "")
    assert ui.mock_calls == [call.created_service_account("service@svc.localhost", "some-group")]
