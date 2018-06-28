from grouper.plugin.base import BasePlugin


class PermissionAliasesPlugin(BasePlugin):
    def get_aliases_for_mapped_permission(self, session, permission, argument):
        if permission != "owner":
            return []

        return [
            ("ssh", "owner={}".format(argument)),
            ("sudo", argument),
        ]
