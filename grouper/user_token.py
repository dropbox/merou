from datetime import datetime

from grouper.models.counter import Counter


def add_new_user_token(session, user_token):
    """Add the new user token specified. If user token doesn't contain a
    secret, create one.

    Args:
        session(grouper.models.base.session.Session): database session
        user_token(grouper.models.user_token.UserToken): token to create

    Returns:
        2-tuple of the created UserToken and the secret
    """
    secret = None
    if user_token.hashed_secret is None:
        secret = user_token._set_secret()

    user_token.add(session)
    Counter.incr(session, "updates")

    return user_token, secret


def disable_user_token(session, user_token):
    """Disable specified user token.

    Args:
        session(grouper.models.base.session.Session): database session
        user_token(grouper.models.user_token.UserToken): token to disable
    """
    user_token.disabled_at = datetime.utcnow()
    Counter.incr(session, "updates")
