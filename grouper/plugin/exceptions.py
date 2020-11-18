class PluginException(Exception):
    pass


class PluginsDirectoryDoesNotExist(PluginException):
    """The specified plugin directory does not exist."""

    pass


class PluginRejectedGroupMembershipUpdate(PluginException):
    pass


class PluginRejectedDisablingUser(PluginException):
    pass


class PluginRejectedMachineSet(PluginException):
    """A plugin rejected a machine set for a service account."""

    pass


class PluginRejectedServiceAccountName(PluginException):
    """A plugin rejected a name for a service account."""

    pass


class PluginRejectedPermissionArgument(PluginException):
    """A plugin rejected a permission argument pairing."""

    pass


class PluginRejectedPublicKey(PluginException):
    pass
