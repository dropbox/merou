from sqlalchemy.orm import Session  # noqa

from grouper.plugin import get_plugins
from grouper.secret import Secret  # noqa


def commit_secret(session, secret):
    # type: (Session, Secret) -> None
    """Commits all changes to the secret (if any) by passing it to the secret management
    plugins.

    Args:
        session: database session

    Throws:
        SecretError (or subclasses) if something doesn't work
    """
    for plugin in get_plugins():
        plugin.commit_secret(session, secret)


def delete_secret(session, secret):
    # type: (Session, Secret) -> None
    """Deletes this secret from the secret management plugins. Continued use of this object
    after calling delete is undefined.

    Args:
        session: database session

    Throws:
        SecretError (or subclasses) if something doesn't work
    """
    for plugin in get_plugins():
        plugin.delete_secret(session, secret)


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
