from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from grouper.models.counter import Counter
from grouper.models.user_password import UserPassword

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.user import User
    from typing import List


class PasswordAlreadyExists(Exception):
    pass


class PasswordDoesNotExist(Exception):
    pass


def add_new_user_password(session, password_name, password, user_id):
    # type: (Session, str, str, int) -> None
    """Add the new user password specified.

    Args:
        session(grouper.models.base.session.Session): database session
        password_name(str): name of the password to be added
        password(str): the (plaintext) password to be added
        user_id(int): the id of the user to add this password to
    """
    p = UserPassword(name=password_name, user_id=user_id)
    p.set_password(password)
    Counter.incr(session, "updates")
    p.add(session)
    try:
        session.commit()
    except IntegrityError:
        raise PasswordAlreadyExists()


def delete_user_password(session, password_name, user_id):
    # type: (Session, str, int) -> None
    """Delete the specified UserPassword.

    Args:
        session(grouper.models.base.session.Session): database session
        password_name: the name of the password to delete
        user_id: the user whose password is being deleted
    """
    p = session.query(UserPassword).filter_by(name=password_name, user_id=user_id).scalar()
    if not p:
        raise PasswordDoesNotExist()
    p.delete(session)
    Counter.incr(session, "updates")
    session.commit()


def user_passwords(session, user):
    # type: (Session, User) -> List[UserPassword]
    """For a given user, return all of its passwords

    Args:
        session(models.base.session.Session): database session
        user(User): user in question
    """
    return session.query(UserPassword).filter_by(user_id=user.id).all()
