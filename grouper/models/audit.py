from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from grouper.models.audit_member import AuditMember
from grouper.models.base.model_base import Model


class Audit(Model):
    # TODO: Extract business logic from this class
    # PLEASE DON'T ADD NEW BUSINESS LOGIC HERE IF YOU CAN AVOID IT!

    """An Audit is applied to a group for a particular audit period

    This contains all of the state of a given audit including each of the members who were
    present in the group at the beginning of the audit period.
    """

    __tablename__ = "audits"

    id = Column(Integer, primary_key=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship("Group", foreign_keys=[group_id])

    # If this audit is complete and when it started/ended
    complete = Column(Boolean, default=False, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ends_at = Column(DateTime, nullable=False)

    # Tracks the last time we emailed the responsible parties of this audit
    last_reminder_at = Column(DateTime, nullable=True)

    def my_members(self):
        """Return all members of this audit

        Only currently valid members (haven't since left the group and haven't joined since the
        audit started).

        Returns:
            list(AuditMember): the members of the audit.
        """

        # Get all members of the audit. Note that this list might change since people can
        # join or leave the group.
        auditmembers = (
            self.session.query(AuditMember).filter(AuditMember.audit_id == self.id).all()
        )

        auditmember_by_edge_id = {am.edge_id: am for am in auditmembers}

        # Now get current members of the group. If someone has left the group, we don't include
        # them in the audit anymore. If someone new joins (or rejoins) then we also don't want
        # to audit them since they had to get approved into the group.
        auditmember_name_pairs = []
        for member in self.group.my_members().values():
            if member.edge_id in auditmember_by_edge_id:
                auditmember_name_pairs.append(
                    (member.name, auditmember_by_edge_id[member.edge_id])
                )

        # Sort by name and return members
        return [auditmember for _, auditmember in sorted(auditmember_name_pairs)]

    @property
    def completable(self):
        """Whether or not this audit is completable

        This is defined as "when all members have been assigned a non-pending status". I.e., at
        that point, we can hit the Complete button which will perform any actions necessary to
        the membership.

        Returns:
            bool: Whether or not this audit can be marked as completed.
        """
        return all([member.status != "pending" for member in self.my_members()])
