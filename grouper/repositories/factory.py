from typing import TYPE_CHECKING

from grouper.repositories.permission import PermissionRepository

if TYPE_CHECKING:
    from grouper.models.base.session import Session


class RepositoryFactory(object):
    """Create repositories, which abstract storage away from the database layer."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def create_permission_repository(self):
        # type: () -> PermissionRepository
        return PermissionRepository(self.session)
