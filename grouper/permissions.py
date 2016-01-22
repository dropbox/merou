from grouper.constants import PERMISSION_GRANT
from grouper.util import matches_glob


def filter_grantable_permissions(session, grants):
    """For a given set of PERMISSION_GRANT permissions, return all permissions
    that are grantable.

    Args:
        session (sqlalchemy.orm.session.Session); database session
        grants ([Permission, ...]): PERMISSION_GRANT permissions

    Returns:
        list of (Permission, argument) that is grantable by list of grants
        sorted by permission name and argument.
    """
    # avoid circular dependency
    from grouper.models import Permission
    all_permissions = {permission.name: permission for permission in Permission.get_all(session)}

    result = []
    for grant in grants:
        assert grant.name == PERMISSION_GRANT

        grantable = grant.argument.split('/', 1)
        if not grantable:
            continue
        for name, permission_obj in all_permissions.iteritems():
            if matches_glob(grantable[0], name):
                result.append((permission_obj,
                               grantable[1] if len(grantable) > 1 else '*', ))

    return sorted(result, key=lambda x: x[0].name + x[1])
