"""Sample plugin that defines a permission alias.

This plugin makes the "owner" permission equivalent to having the "ssh" permission with argument
"owner=<argument>" and the "sudo" permission with argument <argument>, where <argument> is the
argument to the "owner" permission.
"""

from grouper.plugin.base import BasePlugin


class TestPermissionAliasesPlugin(BasePlugin):
    def get_aliases_for_mapped_permission(self, session, permission, argument):
        if permission != "owner":
            return []

        return [("ssh", "owner={}".format(argument)), ("sudo", argument)]
