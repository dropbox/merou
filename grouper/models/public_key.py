from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from grouper.models.base.model_base import Model
from grouper.models.public_key_tag_map import PublicKeyTagMap


def _perm_list_to_dict(perms):
    # type: List[Permission] -> Dict[str, Dict[str, Permission]]
    """Converts a list of Permission objects into a dictionary indexed by the permission names.
    That dictionary in turn holds another dictionary which is indexed by permission argument, and
    stores the Permission object

    Args:
        perms: a list containing Permission objects

    Returns:
        a dictionary with the permission names as keys, and has as values another dictionary
        with permission arguments as keys and Permission objects as values
    """
    ret = dict()
    for perm in perms:
        if perm.name not in ret:
            ret[perm.name] = dict()
        ret[perm.name][perm.argument] = perm
    return ret


def _permission_intersection(perms_a, perms_b):
    # type: List[Permission], List[Permission] -> Set[Permission]
    """Returns the intersection of the two Permission lists, taking into account the special
    handling of argument wildcards

    Args:
        perms_a: the first list of permissions
        perms_b: the second list of permissions

    Returns:
        a set of all permissions that both perms_a and perms_b grant access to
    """
    pdict_b = _perm_list_to_dict(perms_b)
    ret = set()
    for perm in perms_a:
        if perm.name not in pdict_b:
            continue
        if perm.argument in pdict_b[perm.name]:
            ret.add(perm)
            continue
        # Argument wildcard
        if "*" in pdict_b[perm.name]:
            ret.add(perm)
            continue
        # According to Group.has_permission, None as an argument counts as a wildcard too
        if None in pdict_b[perm.name]:
            ret.add(perm)
            continue
        # If this permission is a wildcard, we add all permissions with the same name from
        # the other set
        if perm.argument == "*" or perm.argument is None:
            ret |= {p for p in pdict_b[perm.name].values()}
    return ret


class PublicKey(Model):

    __tablename__ = "public_keys"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])

    key_type = Column(String(length=32))
    key_size = Column(Integer)
    public_key = Column(Text, nullable=False)
    fingerprint = Column(String(length=64), nullable=False, unique=True)
    created_on = Column(DateTime, default=datetime.utcnow, nullable=False)

    def tags(self):
        # type: () -> List[PublicKeyTag]
        """Returns the list of tags that are assigned to this public key

        Returns:
            a list that contains all of the PublicKeyTags that are assigned to this public key
        """
        mappings = self.session.query(PublicKeyTagMap).filter_by(key_id=self.id).all()
        return [mapping.tag for mapping in mappings]

    def my_permissions(self):
        # type: () -> List[Permission]
        """Returns the permissions that this public key has. Namely, this the set of permissions
        that the public key's owner has, intersected with the permissions allowed by this key's
        tags

        Returns:
            a list of all permissions this public key has
        """
        my_perms = self.user.my_permissions()
        for tag in self.tags():
            my_perms = _permission_intersection(my_perms, tag.my_permissions())

        return list(my_perms)

    def pretty_my_permissions(self):
        # type: () -> List[str]
        """Returns a list of this public key's permissions formatted nicely as strings because
        tyleromeara@ got tired of figuring out how to do this in Jinja."""
        return ["{} ({})".format(perm.name, perm.argument if perm.argument else "unargumented")
               for perm in self.my_permissions()]
