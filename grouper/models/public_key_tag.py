from sqlalchemy import Column, Integer, String, Text, Boolean
from grouper.models.base.model_base import Model
from grouper.constants import MAX_NAME_LENGTH
from grouper.models.tag_permission_map import TagPermissionMap
from grouper.models.permission import Permission
from sqlalchemy.sql import label
from grouper.models.audit_log import AuditLog


class PublicKeyTag(Model):

    __tablename__ = "public_key_tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(length=MAX_NAME_LENGTH), unique=True)
    description = Column(Text)
    enabled = Column(Boolean, default=True)

    def my_permissions(self):
        """Returns the permissions granted to this tag.

        Returns:
            A list of namedtuple with the id, name, mapping_id, argument, and granted_on for each
            permission
        """
        permissions = self.session.query(
            Permission.id,
            Permission.name,
            label("mapping_id", TagPermissionMap.id),
            TagPermissionMap.argument,
            TagPermissionMap.granted_on,
        ).filter(
            TagPermissionMap.permission_id == Permission.id,
            TagPermissionMap.tag_id == self.id,
        ).all()

        return permissions

    def my_log_entries(self):
        # type: () -> List[AuditLog]
        """Returns the 20 most recent audit log entries involving this tag

        Returns:
            a list of AuditLog entries
        """
        return AuditLog.get_entries(self.session, on_tag_id=self.id, limit=20)

    @staticmethod
    def get(session, id=None, name=None):
        # type: Session, int, str -> PublicKeyTag
        if id:
            return session.query(PublicKeyTag).filter_by(id=id).scalar()
        if name:
            return session.query(PublicKeyTag).filter_by(name=name).scalar()
        return None
