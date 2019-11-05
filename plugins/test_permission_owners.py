from __future__ import absolute_import, print_function

from typing import TYPE_CHECKING

from grouper.models.group import Group
from grouper.plugin.base import BasePlugin

if TYPE_CHECKING:
    from typing import Dict, List
    from sqlalchemy.orm import Session


class TestPermissionOwnersPlugin(BasePlugin):
    def get_owner_by_arg_by_perm(self, session):
        # type: (Session) -> Dict[str, Dict[str, List[Group]]]
        """Return a map of permissions to owners based on external information."""
        grouper_administrators = (
            session.query(Group).filter(Group.name == "grouper-administrators").first()
        )
        return {
            "sample.permission": {
                "Option A": [grouper_administrators],
                "Option B": [grouper_administrators],
            }
        }
