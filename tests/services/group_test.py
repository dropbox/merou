from typing import TYPE_CHECKING

import pytest

from grouper.constants import DEFAULT_ADMIN_GROUP, ILLEGAL_NAME_CHARACTER
from grouper.entities.group import GroupJoinPolicy, InvalidGroupNameException

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_invalid_group_name(setup):
    # type: (SetupTest) -> None
    group_service = setup.service_factory.create_group_service()
    assert group_service.is_valid_group_name(DEFAULT_ADMIN_GROUP)
    assert not group_service.is_valid_group_name("group name")
    assert not group_service.is_valid_group_name("group{}name".format(ILLEGAL_NAME_CHARACTER))
    with pytest.raises(InvalidGroupNameException):
        group_service.create_group("group name", "", GroupJoinPolicy.NOBODY)
