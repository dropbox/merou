"""
plugin.py

Base plugin for Grouper plugins. These are plugins that can be written to extend Grouper
functionality.
"""
from annex import Annex
from sqlalchemy.orm import Session  # noqa

import grouper  # noqa

Plugins = []  # type: List[BasePlugin]
Secret_Forms = []  # type: List[grouper.secret.Secret]


class PluginsAlreadyLoaded(Exception):
    pass


def load_plugins(plugin_dir, service_name):
    """Load plugins from a directory"""
    global Plugins
    if Plugins:
        raise PluginsAlreadyLoaded("Plugins already loaded; can't load twice!")
    Plugins = Annex(BasePlugin, [plugin_dir], raise_exceptions=True)
    global Secret_Forms
    for plugin in Plugins:
        plugin.configure(service_name)
        Secret_Forms += plugin.get_secret_forms()


def get_plugins():
    """Get a list of loaded plugins."""
    global Plugins
    return list(Plugins)


def get_secret_forms():
    # type: () -> List[grouper.secret.Secret]
    """Get a list of all Secret subclasses

    Returns:
        a copy of the list of all secret subclasses supported by loaded plugins
    """
    global Secret_Forms
    return list(Secret_Forms)


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

    def get_secret_forms(self):
        # type: () -> List[grouper.secret.Secret]
        """Called when the plugin is instantiated to determine what secret
        subclasses the plugins supports (if any).

        Returns:
            a list of the Secret subclasses that this plugin exposes (if any). Empty list otherwise
        """
        return []

    def commit_secret(self, session, secret):
        # type: (Session, grouper.secret.Secret) -> None
        """Passes a Secret object to the plugin for processing, saving, distribution, and all of
        the other things secret management systems do when creating or updating a secret.

        Args:
            session: database session
            secret: the Secret to be committed

        Throws:
            Any exceptions should be a subclass of SecretError

        Returns:
            Nothing
        """
        pass

    def delete_secret(self, session, secret):
        # type: (Session, grouper.secret.Secret) -> None
        """Passes a Secret object to the plugin to be deleted and removed from the secret
        management sysmte.

        Args:
            session: database session
            secret: the Secret to be deleted

        Throws:
            Any exceptions should be a subclass of SecretError

        Returns:
            Nothing
        """
        pass

    def get_secrets(self, session):
        # type: (Session) -> Dict[str, grouper.secret.Secret]
        """Returns a dict of all secrets this plugin manages, keyed by the secret's name. The
        secrets must not contain any information that should not be exposed to the user, such
        as the value of the secret itself. If the plugin uses 1 or more fields of the Secret
        type (or a subclass) for storing the secret, those fields must be replaced with
        nonsensitive information before this method returns; even if the fields are not part
        of the standard Secret interface.

        Args:
            session: database session

        Throws:
            Any exceptions should be a subclass of SecretError

        Returns:
            a dictionary that contains all secrets that this plugin manages, or an empty dictionary
        """
        return {}

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

    def log_auditlog_entry(self, entry):
        """
        Called when an audit log entry is saved to the database.

        Args:
            entry (models.audit_log.AuditLog): just-saved log object
        """
        pass
