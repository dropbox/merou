from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from grouper.models.base.model_base import Model
from grouper.models.public_key_tag_map import PublicKeyTagMap


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
        from grouper.permissions import permission_intersection
        # TODO: Fix underlying circular dependency

        my_perms = self.user.my_permissions()
        for tag in self.tags():
            my_perms = permission_intersection(my_perms, tag.my_permissions())

        return list(my_perms)

    def pretty_my_permissions(self):
        # type: () -> List[str]
        """Returns a list of this public key's permissions formatted nicely as strings because
        tyleromeara@ got tired of figuring out how to do this in Jinja."""
        return ["{} ({})".format(perm.name, perm.argument if perm.argument else "unargumented")
               for perm in self.my_permissions()]
