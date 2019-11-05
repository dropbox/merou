from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_permission_grants_for_user(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_user("gary@a.co")

    permission_grant_repository = setup.sql_repository_factory.create_permission_grant_repository()
    assert permission_grant_repository.permission_grants_for_user("gary@a.co") == []

    # Build a bit of a group hierarchy with some nested inheritance.
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "one-group")
        setup.grant_permission_to_group("perm", "one", "one-group")
        setup.add_user_to_group("gary@a.co", "two-group", "owner")
        setup.grant_permission_to_group("perm", "two", "two-group")
        setup.add_user_to_group("gary@a.co", "three-group", "np-owner")
        setup.grant_permission_to_group("perm", "three", "three-group")
        setup.add_group_to_group("one-group", "parent")
        setup.grant_permission_to_group("other-perm", "arg", "parent")
        setup.add_group_to_group("parent", "grandparent")
        setup.grant_permission_to_group("other-perm", "arg", "grandparent")
        setup.grant_permission_to_group("other-perm", "*", "grandparent")
        setup.add_group_to_group("two-group", "grandparent")
        setup.add_group_to_group("three-group", "np-group")
        setup.grant_permission_to_group("another-perm", "foo", "np-group")

    # Check the returned permissions.
    permission_grants = permission_grant_repository.permission_grants_for_user("gary@a.co")
    assert sorted([(p.permission, p.argument) for p in permission_grants]) == [
        ("other-perm", "*"),
        ("other-perm", "arg"),
        ("other-perm", "arg"),
        ("perm", "one"),
        ("perm", "two"),
    ]


def test_permission_grants_for_group(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_group("one-group")

    permission_grant_repository = setup.sql_repository_factory.create_permission_grant_repository()
    assert permission_grant_repository.permission_grants_for_group("one-group") == []

    # Build a bit of a group hierarchy with some nested inheritance.
    with setup.transaction():
        setup.grant_permission_to_group("perm", "one", "one-group")
        setup.add_group_to_group("one-group", "parent")
        setup.grant_permission_to_group("other-perm", "arg", "parent")
        setup.add_group_to_group("parent", "grandparent")
        setup.grant_permission_to_group("other-perm", "arg", "grandparent")
        setup.grant_permission_to_group("other-perm", "*", "grandparent")
        setup.grant_permission_to_group("perm", "two", "two-group")
        setup.grant_permission_to_group("another-perm", "foo", "np-group")

    # Check the returned permissions.
    permission_grants = permission_grant_repository.permission_grants_for_group("one-group")
    assert sorted([(p.permission, p.argument) for p in permission_grants]) == [
        ("other-perm", "*"),
        ("other-perm", "arg"),
        ("other-perm", "arg"),
        ("perm", "one"),
    ]
