from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, SmallInteger
from sqlalchemy.orm import relationship

from grouper.entities.group_edge import GROUP_EDGE_ROLES, OWNER_ROLE_INDICES
from grouper.expiration import add_expiration, cancel_expiration
from grouper.models.base.constants import OBJ_TYPES_IDX
from grouper.models.base.model_base import Model
from grouper.models.user import User

if TYPE_CHECKING:
    from typing import Any, Dict


class GroupEdge(Model):
    # TODO: Extract business logic from this class
    # PLEASE DON'T ADD NEW BUSINESS LOGIC HERE IF YOU CAN AVOID IT!

    __tablename__ = "group_edges"
    __table_args__ = (
        Index("group_member_idx", "group_id", "member_type", "member_pk", unique=True),
        Index("group_edges_member_pk_type", "member_pk", "member_type"),
    )

    id = Column(Integer, primary_key=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship("Group", backref="edges", foreign_keys=[group_id])

    member_type = Column(Integer, nullable=False)
    member_pk = Column(Integer, nullable=False)

    expiration = Column(DateTime)
    active = Column(Boolean, default=False, nullable=False)
    _role = Column(SmallInteger, default=0, nullable=False)

    @property
    def role(self):
        # type: () -> str
        return GROUP_EDGE_ROLES[self._role]

    @role.setter
    def role(self, role):
        # type: (str) -> None
        prev_role = self._role
        self._role = GROUP_EDGE_ROLES.index(role)

        # Groups should always "member".
        if not (OBJ_TYPES_IDX[self.member_type] == "User"):
            return

        # If ownership status is unchanged, no notices need to be adjusted.
        if (self._role in OWNER_ROLE_INDICES) == (prev_role in OWNER_ROLE_INDICES):
            return

        user = User.get(self.session, pk=self.member_pk)
        assert user
        recipient = user.username
        expiring_supergroups = self.group.my_expiring_groups()
        member_name = self.group.name

        if role in ["owner", "np-owner"]:
            # We're creating a new owner, who should find out when this group
            # they now own loses its membership in larger groups.
            for supergroup_name, expiration in expiring_supergroups:
                add_expiration(
                    self.session,
                    expiration,
                    group_name=supergroup_name,
                    member_name=member_name,
                    recipients=[recipient],
                    member_is_user=False,
                )
        else:
            # We're removing an owner, who should no longer find out when this
            # group they no longer own loses its membership in larger groups.
            for supergroup_name, _ in expiring_supergroups:
                cancel_expiration(
                    self.session,
                    group_name=supergroup_name,
                    member_name=member_name,
                    recipients=[recipient],
                )

    def apply_changes(self, changes):
        # type: (Dict[str, Any]) -> None
        # TODO(cbguder): get around circular dependencies
        from grouper.models.group import Group

        for key, value in changes.items():
            if key == "expiration":
                group_name = self.group.name
                if OBJ_TYPES_IDX[self.member_type] == "User":
                    # If affected member is a user, plan to notify that user.
                    user = User.get(self.session, pk=self.member_pk)
                    assert user
                    member_name = user.username
                    recipients = [member_name]
                    member_is_user = True
                else:
                    # Otherwise, affected member is a group, notify its owners.
                    subgroup = Group.get(self.session, pk=self.member_pk)
                    assert subgroup, "Group edge refers to nonexistent group"
                    member_name = subgroup.groupname
                    recipients = subgroup.my_owners_as_strings()
                    member_is_user = False
                if getattr(self, key, None) is not None:
                    # Check for and remove pending expiration notification.
                    cancel_expiration(self.session, group_name, member_name)
                if value:
                    expiration = datetime.strptime(value, "%m/%d/%Y")
                    setattr(self, key, expiration)
                    # Avoid sending notifications for expired edges.
                    if expiration > datetime.utcnow():
                        add_expiration(
                            self.session,
                            expiration,
                            group_name,
                            member_name,
                            recipients=recipients,
                            member_is_user=member_is_user,
                        )
                else:
                    setattr(self, key, None)
            else:
                setattr(self, key, value)

    def __repr__(self):
        return "%s(group_id=%s, member_type=%s, member_pk=%s)" % (
            type(self).__name__,
            self.group_id,
            OBJ_TYPES_IDX[self.member_type],
            self.member_pk,
        )
