from collections import defaultdict

from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import label
import sshpubkeys

from grouper.models.base.session import Session  # noqa
from grouper.models.counter import Counter
from grouper.models.permission import Permission
from grouper.models.public_key import PublicKey
from grouper.models.public_key_tag import PublicKeyTag  # noqa
from grouper.models.public_key_tag_map import PublicKeyTagMap
from grouper.models.tag_permission_map import TagPermissionMap
from grouper.user_permissions import user_permissions


class DuplicateKey(Exception):
    pass


class DuplicateTag(Exception):
    pass


class KeyNotFound(Exception):
    key_id = None  # type: int
    user_id = None  # type: int
    """Particular user's specific key was not found."""


class TagNotOnKey(Exception):
    key_id = None  # type: int
    tag_id = None  # type: int


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
    pubkey = sshpubkeys.SSHKey(public_key_str, strict=True)
    pubkey.parse()

    db_pubkey = PublicKey(
        user=user,
        public_key=pubkey.keydata.strip(),
        fingerprint=pubkey.hash_md5().replace(b"MD5:", b""),
        key_size=pubkey.bits,
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
    """Delete a particular user's public key. This will remove all
        tags from the public key prior to deletion.

    Args:
        session(models.base.session.Session): database session
        user_id(int): id of user in question
        key_id(int): id of the user's key we want to delete

    Throws:
        KeyNotFound if specified key wasn't found
    """
    pkey = get_public_key(session, user_id, key_id)

    tag_mappings = session.query(PublicKeyTagMap).filter_by(key_id=key_id).all()
    for mapping in tag_mappings:
        remove_tag_from_public_key(session, pkey, mapping.tag)

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
    # type: (Session, PublicKey, PublicKeyTag) -> None
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
    # type: (Session, PublicKey, PublicKeyTag) -> None
    """Removes the tag from the given public key.

    Args:
        session(models.base.session.Session): database session
        public_key(models.public_key.PublicKey): the public key to be tagged
        tag(models.public_key_tag.PublicKeyTag): the tag to be removed from the public key

    Throws:
        TagNotOnKey if the tag was already assigned to the public key
    """
    mapping = session.query(PublicKeyTagMap).filter_by(tag_id=tag.id, key_id=public_key.id).scalar()

    if not mapping:
        raise TagNotOnKey()

    mapping.delete(session)
    Counter.incr(session, "updates")
    session.commit()


def get_all_public_key_tags(session):
    # type: (Session) -> Dict[int, List[PublicKeyTag]]
    """Returns a dict with all tags that are assigned to each public key

    Args:
        session: database session

    Returns:
        A dictionary that has all PublicKeyTags assigned to any public key
    """
    ret = defaultdict(list)  # type: Dict[int, List[PublicKeyTag]]
    for mapping in session.query(PublicKeyTagMap).all():
        ret[mapping.key.id].append(mapping.tag)
    return ret


def get_public_key_tags(session, public_key):
    # type: (Session, PublicKey) -> List[PublicKeyTag]
    """Returns the list of tags that are assigned to this public key

    Returns:
        a list that contains all of the PublicKeyTags that are assigned to this public key
    """
    mappings = session.query(PublicKeyTagMap).filter_by(key_id=public_key.id).all()
    return [mapping.tag for mapping in mappings]


def get_public_key_permissions(session, public_key):
    # type: (Session, PublicKey) -> List[Permission]
    """Returns the permissions that this public key has. Namely, this the set of permissions
    that the public key's owner has, intersected with the permissions allowed by this key's
    tags

    Returns:
        a list of all permissions this public key has
    """
    # TODO: Fix circular dependency
    from grouper.permissions import permission_intersection
    my_perms = user_permissions(session, public_key.user)
    for tag in get_public_key_tags(session, public_key):
        my_perms = permission_intersection(my_perms,
            get_public_key_tag_permissions(session, tag))

    return list(my_perms)


def get_public_key_tag_permissions(session, tag):
    """Returns the permissions granted to this tag.

    Returns:
        A list of namedtuple with the id, name, mapping_id, argument, and granted_on for each
        permission
    """
    permissions = session.query(
        Permission.id,
        Permission.name,
        label("mapping_id", TagPermissionMap.id),
        TagPermissionMap.argument,
        TagPermissionMap.granted_on,
    ).filter(
        TagPermissionMap.permission_id == Permission.id,
        TagPermissionMap.tag_id == tag.id,
    ).all()

    return permissions
