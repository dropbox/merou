import sshpubkeys
from sqlalchemy.exc import IntegrityError

from grouper.models.counter import Counter
from grouper.models.public_key import PublicKey
from grouper.plugin import get_plugin_proxy
from grouper.plugin.exceptions import PluginRejectedPublicKey


class DuplicateKey(Exception):
    pass


class PublicKeyParseError(Exception):
    pass


class BadPublicKey(Exception):
    pass


class KeyNotFound(Exception):
    """Particular user's specific key was not found."""

    def __init__(self, key_id, user_id):
        # type: (int, int) -> None
        self.key_id = key_id
        self.user_id = user_id


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

    Throws:
        DuplicateKey if key is already in use
        PublicKeyParseError if key can't be parsed
        BadPublicKey if a plugin rejects the key

    Returns:
        PublicKey model object representing the key
    """
    pubkey = sshpubkeys.SSHKey(public_key_str, strict=True)

    try:
        pubkey.parse()
    except sshpubkeys.InvalidKeyException as e:
        raise PublicKeyParseError(str(e))

    # Allowing newlines can lead to injection attacks depending on how the key is
    # consumed, such as if it's dumped in an authorized_keys file with a `command`
    # restriction.
    # Note parsing the key is insufficient to block this.
    if "\r" in public_key_str or "\n" in public_key_str:
        raise PublicKeyParseError("Public key cannot have newlines")

    try:
        get_plugin_proxy().will_add_public_key(pubkey)
    except PluginRejectedPublicKey as e:
        raise BadPublicKey(str(e))

    db_pubkey = PublicKey(
        user=user,
        public_key=pubkey.keydata.strip(),
        fingerprint=pubkey.hash_md5().replace("MD5:", ""),
        fingerprint_sha256=pubkey.hash_sha256().replace("SHA256:", ""),
        key_size=pubkey.bits,
        key_type=pubkey.key_type,
        comment=pubkey.comment,
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
