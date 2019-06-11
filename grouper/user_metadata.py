import re
from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_VALIDATION
from grouper.models.counter import Counter
from grouper.models.user_metadata import UserMetadata

if TYPE_CHECKING:
    from typing import Optional, Sequence
    from grouper.models.base.session import Session


def get_user_metadata(session, user_id):
    # type: (Session, int) -> Sequence[UserMetadata]
    """Return all of a user's metadata.

    Args:
        session(models.base.session.Session): database session
        user_id(int): id of user in question

    Returns:
        List of UserMetadata objects
    """
    return session.query(UserMetadata).filter(UserMetadata.user_id == user_id).all()


def get_user_metadata_by_key(session, user_id, data_key):
    # type: (Session, int, str) -> UserMetadata
    """Return the user's metadata if it has the matching key

    Args:
        session(models.base.session.Session): database session
        user_id(int): id of user in question

    Returns:
        A UserMetadata object
    """
    return session.query(UserMetadata).filter_by(user_id=user_id, data_key=data_key).scalar()


def set_user_metadata(session, user_id, data_key, data_value):
    # type: (Session, int, str, str) -> Optional[UserMetadata]
    """Set a single piece of user metadata.

    Args:
        session(models.base.session.Session): database session
        user_id(int): id of user in question
        data_key(str): the metadata key (limited to 64 character by db schema)
        data_value(str):  the metadata value (limited to 64 character by db
                schema) if this is None, the metadata entry is deleted.

    Returns:
        the UserMetadata object or None if entry was deleted
    """
    assert re.match(PERMISSION_VALIDATION, data_key), "proposed metadata key is valid"

    user_md = get_user_metadata_by_key(session, user_id, data_key)

    if user_md:
        if data_value is None:
            user_md.delete(session)
            user_md = None
        else:
            user_md.data_value = data_value
            user_md.add(session)
    else:
        if data_value is None:
            # do nothing, a delete on a key that's not set
            return
        else:
            user_md = UserMetadata(user_id=user_id, data_key=data_key, data_value=data_value)
            user_md.add(session)

    Counter.incr(session, "updates")
    session.commit()

    return user_md
