"""
plugin.py

Base plugin for Grouper plugins. These are plugins that can be written to extend Grouper
functionality.
"""
from importlib import import_module
import inspect
import os
from typing import TYPE_CHECKING

from annex import Annex

if TYPE_CHECKING:
    from ssl import SSLContext  # noqa
    from typing import Any, Dict, List, Union  # noqa
    from sqlalchemy.orm import Session  # noqa
    from tornado.httpserver import HTTPRequest  # noqa
    from grouper.models.audit_log import AuditLog  # noqa
    from grouper.models.group import Group  # noqa
    from grouper.models.user import User  # noqa

Plugins = []  # type: List[BasePlugin]


class PluginException(Exception):
    pass


class PluginsDirectoryDoesNotExist(PluginException):
    """The specified plugin direcotry does not exist."""


class PluginsAlreadyLoaded(PluginException):
    """`load_plugins()` called twice."""


def load_plugins(plugin_dir, plugin_module_paths, service_name):
    # type: (str, List[str], str) -> None
    """Load plugins from a directory"""
    global Plugins
    if Plugins:
        raise PluginsAlreadyLoaded("Plugins already loaded; can't load twice!")

    if plugin_dir:
        if not os.path.exists(plugin_dir):
            raise PluginsDirectoryDoesNotExist("{} doesn't exist".format(plugin_dir))

        plugin_dirs = [plugin_dir]
    else:
        plugin_dirs = []

    Plugins = Annex(BasePlugin, plugin_dirs, raise_exceptions=True,
            additional_plugin_callback=load_plugin_modules(plugin_module_paths))

    for plugin in Plugins:
        plugin.configure(service_name)


def load_plugin_modules(plugin_module_paths):
    def callback():
        plugins = []
        if plugin_module_paths:
            for module_path in plugin_module_paths:
                module = import_module(module_path)
                for name in dir(module):
                    obj = getattr(module, name)
                    if inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj != BasePlugin:
                        plugins.append(obj)

        return plugins
    return callback


def get_plugins():
    # type: () -> List[BasePlugin]
    """Get a list of loaded plugins."""
    global Plugins
    return list(Plugins)


class PluginRejectedGroupMembershipUpdate(PluginException):
    pass


class PluginRejectedDisablingUser(PluginException):
    pass


class BasePlugin(object):
    def user_created(self, user):
        # type: (User) -> None
        """Called when a new user is created

        When new users enter into Grouper, you might have reason to set metadata on those
        users for some reason. This method is called when that happens.

        Args:
            user: Object of new user.

        Returns:
            The return code of this method is ignored.
        """
        pass

    def configure(self, service_name):
        # type: (str) -> None
        """
        Called once the plugin is instantiated to identify the executable
        (grouper-api or grouper-fe).
        """
        pass

    def get_ssl_context(self):
        # type: () -> SSLContext
        """
        Called to get the ssl.SSLContext for the application.
        """
        pass

    def log_exception(self, request, status, exception, stack):
        # type: (HTTPRequest, int, Exception, List) -> None
        """
        Called when responding with statuses 400, 403, 404, and 500.

        Args:
            request: the request being handled.
            status: the response status.
            exception: either a tornado.web.HTTPError or an unexpected exception.
            stack: "pre-processed" stack trace entries for traceback.format_list.

        Returns:
            The return code of this method is ignored.
        """
        pass

    def get_owner_by_arg_by_perm(self, session):
        # type: (Session) -> Dict[str, Dict[str, Group]]
        """Called when determining owners for permission+arg granting.

        Args:
            session: database session

        Returns:
            dict of the form {'permission_name': {'argument': [owner1, owner2,
            ...], ...}, ...} where 'ownerN' is a models.Group corresponding to
            the grouper group that owns (read: is able to) grant that
            permission + argument pair.
        """
        pass

    def log_auditlog_entry(self, entry):
        # type: (AuditLog) -> None
        """
        Called when an audit log entry is saved to the database.

        Args:
            entry: just-saved log object
        """
        pass

    def will_update_group_membership(self, session, group, member, **updates):
        # type: (Session, Group, Union[User, Group], **Any) -> None
        """
        Called before applying changes to a group membership

        Args:
            session: database session
            group: affected group
            member: affected User or Group
            updates: the updates to the membership (active, expiration, role)

        Raises:
            PluginRejectedGroupMembershipUpdate: if the plugin rejects the update
        """
        pass

    def will_disable_user(self, session, user):
        # type: (Session, User) -> None
        """
        Called before disabling a user

        Args:
            session: database session
            user: User to be disabled

        Raises:
            PluginRejectedDisablingUser: if the plugin rejects the change
        """
        pass
