from sqlalchemy.exc import IntegrityError
import sshpubkey
from sshpubkey.exc import PublicKeyParseError  # noqa

from .models import PublicKey


class DuplicateKey(Exception):
    pass


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
    except IntegrityError:
        session.rollback()
        raise DuplicateKey()

    session.commit()

    return db_pubkey
