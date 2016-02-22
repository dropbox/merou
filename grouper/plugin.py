"""
plugin.py

Base plugin for Grouper plugins. These are plugins that can be written to extend Grouper
functionality.
"""
from annex import Annex


Plugins = []


class PluginsAlreadyLoaded(Exception):
    pass


def load_plugins(plugin_dir, service_name):
    """Load plugins from a directory"""
    global Plugins
    if Plugins:
        raise PluginsAlreadyLoaded("Plugins already loaded; can't load twice!")
    Plugins = Annex(BasePlugin, [plugin_dir], raise_exceptions=True)
    for plugin in Plugins:
        plugin.configure(service_name)


def get_plugins():
    """Get a list of loaded plugins."""
    global Plugins
    return list(Plugins)


class BasePlugin(object):
    def user_created(self, user):
        """Called when a new user is created

        When new users enter into Grouper, you might have reason to set metadata on those
        users for some reason. This method is called when that happens.

        Args:
            user (models.User): Object of new user.

        Returns:
            The return code of this method is ignored.
        """
        pass

    def configure(self, service_name):
        """
        Called once the plugin is instantiated to identify the executable
        (grouper-api or grouper-fe).
        """
        pass

    def log_exception(self, request, status, exception, stack):
        """
        Called when responding with statuses 400, 403, 404, and 500.

        Args:
            request (tornado.httputil.HTTPServerRequest): the request being handled.
            status (int): the response status.
            exception (Exception): either a tornado.web.HTTPError or an unexpected exception.
            stack (list): "pre-processed" stack trace entries for traceback.format_list.

        Returns:
            The return code of this method is ignored.
        """
        pass

    def get_owner_by_arg_by_perm(self, session):
        """Called when determining owners for permission+arg granting.

        Args:
            session(sqlalchemy.orm.session.Session): database session

        Returns:
            dict of the form {'permission_name': {'argument': [owner1, owner2,
            ...], ...}, ...} where 'ownerN' is a models.Group corresponding to
            the grouper group that owns (read: is able to) grant that
            permission + argument pair.
        """
        pass
