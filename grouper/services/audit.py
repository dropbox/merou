from typing import TYPE_CHECKING

from grouper.entities.audit import GroupAuditDetails
from grouper.usecases.interfaces import AuditInterface

if TYPE_CHECKING:
    from grouper.entities.audit import GroupAuditInfo
    from grouper.repositories.interfaces import (
        AuditRepository,
        PermissionGrantRepository,
        PermissionRepository,
    )
    from typing import Optional


class AuditService(AuditInterface):
    """High-level logic for audits."""

    def __init__(self, audit_repository, permission_repository, permission_grant_repository):
        # type: (AuditRepository, PermissionRepository, PermissionGrantRepository) -> None
        self.audit_repository = audit_repository
        self.permission_repository = permission_repository
        self.permission_grant_repository = permission_grant_repository

    def is_group_audited(self, groupname):
        # type: (str) -> bool
        for gpg in self.permission_grant_repository.permission_grants_for_group(groupname):
            permission_info = self.permission_repository.get_permission(gpg.permission)
            if permission_info and permission_info.audited:
                return True
        return False

    def group_pending_audit_info(self, groupname):
        # type: (str) -> Optional[GroupAuditInfo]
        return self.audit_repository.group_pending_audit_info(groupname)

    def group_pending_audit_details(self, groupname):
        # type: (str) -> Optional[GroupAuditDetails]
        audit_info = self.audit_repository.group_pending_audit_info(groupname)
        if audit_info:
            audit_members_infos = self.audit_repository.group_audit_members_infos(
                groupname, audit_info.id
            )
            return GroupAuditDetails(
                id=audit_info.id,
                complete=audit_info.complete,
                started_at=audit_info.started_at,
                ends_at=audit_info.ends_at,
                audit_members_infos=audit_members_infos,
            )
        else:
            return None
