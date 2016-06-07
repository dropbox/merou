from grouper.model_soup import Group, User


def get_user_or_group(session, name, user_or_group=None):
    """Given a name, fetch a user or group

    If user_or_group is not defined, we determine whether a the name refers to
    a user or group by checking whether the name is an email address, since
    that's how users are specified.

    Args:
        session (Session): Session to load data on.
        name (str): The name of the user or group.
        user_or_group(str): "user" or "group" to specify the type explicitly

    Returns:
        User or Group object.
    """
    if user_or_group is not None:
        assert (user_or_group in ["user", "group"]), ("%s not in ['user', 'group']" % user_or_group)
        is_user = (user_or_group == "user")
    else:
        is_user = '@' in name

    if is_user:
        return session.query(User).filter_by(username=name).scalar()
    else:
        return session.query(Group).filter_by(groupname=name).scalar()


def get_all_users(session):
    """Returns all valid users in the group.

    At present, this is not cached at all and returns the full list of
    users from the database each time it's called.

    Args:
        session (Session): Session to load data on.

    Returns:
        a list of all User objects in the database
    """
    return session.query(User).all()


def get_all_enabled_users(session):
    # type: Session -> List[User]
    """Returns all enabled users in the database.

    At present, this is not cached at all and returns the full list of
    users from the database each time it's called.

    Args:
        session (Session): Session to load data on.

    Returns:
        a list of all enabled User objects in the database
    """
    return session.query(User).filter_by(enabled=True).all()
