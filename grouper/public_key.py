from sqlalchemy.exc import IntegrityError
import sshpubkey
from sshpubkey.exc import PublicKeyParseError  # noqa

from grouper.models.counter import Counter
from grouper.models.public_key import PublicKey


class DuplicateKey(Exception):
    pass


class KeyNotFound(Exception):
    key_id = None
    user_id = None
    """Particular user's specific key was not found."""


def get_public_key(session, user_id, key_id):
    """Retrieve specific public key for user.

    Args:
        session(models.base.session.Session): database session
        user_id(int): id of user in question
        key_id(int): id of the user's key we want to delete

    Throws:
        KeyNotFound if specified key wasn't found

    Returns:
        PublicKey model object representing the key
    """
    pkey = session.query(PublicKey).filter_by(id=key_id, user_id=user_id).scalar()
    if not pkey:
        raise KeyNotFound(key_id=key_id, user_id=user_id)

    return pkey


def add_public_key(session, user, public_key_str):
    """Add a public key for a particular user.

    Args:
        session: db session
        user: User model of user in question
        public_key_str: public key to add

    Return created PublicKey model or raises DuplicateKey if key is already in use.
    """
    pubkey = sshpubkey.PublicKey.from_str(public_key_str)
    db_pubkey = PublicKey(
        user=user,
        public_key='%s %s %s' % (pubkey.key_type, pubkey.key, pubkey.comment),
        fingerprint=pubkey.fingerprint,
        key_size=pubkey.key_size,
        key_type=pubkey.key_type,
    )
    try:
        db_pubkey.add(session)
        Counter.incr(session, "updates")
    except IntegrityError:
        session.rollback()
        raise DuplicateKey()

    session.commit()

    return db_pubkey


def delete_public_key(session, user_id, key_id):
    """Delete a particular user's public key.

    Args:
        session(models.base.session.Session): database session
        user_id(int): id of user in question
        key_id(int): id of the user's key we want to delete

    Throws:
        KeyNotFound if specified key wasn't found
    """
    pkey = get_public_key(session, user_id, key_id)
    pkey.delete(session)

    Counter.incr(session, "updates")

    session.commit()
