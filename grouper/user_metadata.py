import re

from grouper.constants import PERMISSION_VALIDATION
from grouper.models.counter import Counter
from grouper.models.user_metadata import UserMetadata


class MetadataNotFound(Exception):
    """Particualr user metadata entry was not found."""
    user_id = None
    data_key = None


def get_user_metadata(session, user_id):
    """Return all of a user's metadata.

    Args:
        session(models.base.session.Session): database session
        user_id(int): id of user in question

    Returns:
        List of UserMetadata objects
    """
    return session.query(UserMetadata).filter(UserMetadata.user_id == user_id).all()


def set_user_metadata(session, user_id, data_key, data_value):
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
    assert re.match(PERMISSION_VALIDATION, data_key), 'proposed metadata key is valid'

    user_md = None
    for try_user_md in get_user_metadata(session, user_id):
        if try_user_md.data_key == data_key:
            user_md = try_user_md
            break

    if user_md:
        if data_value is None:
            user_md.delete(session)
            Counter.incr(session, "updates")
            user_md = None
        else:
            user_md.data_value = data_value
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
