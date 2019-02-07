class PluginException(Exception):
    pass


class PluginsDirectoryDoesNotExist(PluginException):
    """The specified plugin directory does not exist."""


class PluginRejectedGroupMembershipUpdate(PluginException):
    pass


class PluginRejectedDisablingUser(PluginException):
    pass


class PluginRejectedMachineSet(PluginException):
    """A plugin rejected a machine set for a service account."""

    pass


class PluginRejectedPublicKey(PluginException):
    pass
