from sqlalchemy.exc import IntegrityError
import sshpubkey
from sshpubkey.exc import PublicKeyParseError  # noqa

from grouper.models.counter import Counter
from grouper.models.public_key import PublicKey
from grouper.models.public_key_tag_map import PublicKeyTagMap


class DuplicateKey(Exception):
    pass


class DuplicateTag(Exception):
    pass


class KeyNotFound(Exception):
    key_id = None
    user_id = None
    """Particular user's specific key was not found."""


class TagNotOnKey(Exception):
    key_id = None
    tag_id = None


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

    tags = session.query(PublicKeyTagMap).filter_by(key_id=key_id).all()
    for tag in tags:
        remove_tag_from_public_key(session, pkey, tag)

    pkey.delete(session)

    Counter.incr(session, "updates")

    session.commit()


def get_public_keys_of_user(session, user_id):
    """Retrieve all public keys for user.

    Args:
        session(models.base.session.Session): database session
        user_id(int): id of user in question

    Returns:
        List of PublicKey model object representing the keys
    """
    pkey = session.query(PublicKey).filter_by(user_id=user_id).all()
    return pkey


def add_tag_to_public_key(session, public_key, tag):
    # type: Session, PublicKey, PublicKeyTag -> None
    """Assigns the tag to the given public key.

    Args:
        session(models.base.session.Session): database session
        public_key(models.public_key.PublicKey): the public key to be tagged
        tag(models.public_key_tag.PublicKeyTag): the tag to be assigned to the public key

    Throws:
        DuplicateTag if the tag was already assigned to the public key
    """
    mapping = PublicKeyTagMap(tag_id=tag.id, key_id=public_key.id)
    try:
        mapping.add(session)
        Counter.incr(session, "updates")
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DuplicateTag()


def remove_tag_from_public_key(session, public_key, tag):
    # type: Session, PublicKey, PublicKeyTag -> None
    """Removes the tag from the given public key.

    Args:
        session(models.base.session.Session): database session
        public_key(models.public_key.PublicKey): the public key to be tagged
        tag(models.public_key_tag.PublicKeyTag): the tag to be assigned to the public key

    Throws:
        TagNotOnKey if the tag was already assigned to the public key
    """
    mapping = session.query(PublicKeyTagMap).filter_by(tag_id=tag.id, key_id=public_key.id).scalar()

    if not mapping:
        raise TagNotOnKey()

    mapping.delete(session)
    Counter.incr(session, "updates")
    session.commit()
