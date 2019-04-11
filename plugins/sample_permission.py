from __future__ import absolute_import, print_function

import json
import logging

from collections import defaultdict
from typing import TYPE_CHECKING

import yaml

from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.plugin.base import BasePlugin


if TYPE_CHECKING:
    from typing import Dict, List
    from sqlalchemy.orm import Session


class PermissionRequest(BasePlugin):
    def get_owner_by_arg_by_perm(self, session):
        # type: (Session) -> Dict[str, Dict[str, List[Group]]]
        """Return a map of permissions to owners based on external information."""
        return {
            'sample.permission': {
                'Option A': ['grouper-administrators'],
                'Option B': ['grouper-administrators'],
            }
        }
