from sqlalchemy.orm import Session  # noqa

from grouper.models.user import User  # noqa
from grouper.plugin import get_plugins
from grouper.secret import Secret  # noqa


def commit_secret(session, secret, actor):
    # type: (Session, Secret, User) -> None
    """Commits all changes to the secret (if any) by passing it to the secret management
    plugins.

    Args:
        session: database session
        secret: the secret to be committed
        actor: the user who made the change to the secret

    Throws:
        SecretError (or subclasses) if something doesn't work
    """
    for plugin in get_plugins():
        plugin.commit_secret(session, secret, actor)


def delete_secret(session, secret, actor):
    # type: (Session, Secret, User) -> None
    """Deletes this secret from the secret management plugins. Continued use of this object
    after calling delete is undefined.

    Args:
        session: database session
        secret: the secret to be committed
        actor: the user who made the change to the secret

    Throws:
        SecretError (or subclasses) if something doesn't work
    """
    for plugin in get_plugins():
        plugin.delete_secret(session, secret, actor)


def get_all_secrets(session):
    # type: (Session) -> Dict[str, Secret]
    """Returns a dictionary with every secret that is managed.

    Returns:
        A dictionary keyed by secret names of all secrets
    """
    ret = {}  # type: Dict[str, Secret]
    for plugin in get_plugins():
        ret.update(plugin.get_secrets(session))
    return ret


def get_token_secret_form():
    for plugin in get_plugins():
        ret = plugin.get_token_secret_form()
        if ret:
            return ret
    return None


def get_ssh_key_secret_form():
    for plugin in get_plugins():
        ret = plugin.get_ssh_key_secret_form()
        if ret:
            return ret
    return None
