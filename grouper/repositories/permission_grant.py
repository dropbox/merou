from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import or_

from grouper.entities.group import GroupNotFoundException
from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.entities.pagination import (
    PaginatedList,
    PermissionGroupGrantSortKey,
    PermissionServiceAccountGrantSortKey,
)
from grouper.entities.permission import PermissionNotFoundException
from grouper.entities.permission_grant import (
    GroupPermissionGrant,
    ServiceAccountPermissionGrant,
    UniqueGrantsOfPermission,
)
from grouper.entities.service_account import ServiceAccountNotFoundException
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.permission import Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.service_account import ServiceAccount
from grouper.models.service_account_permission_map import ServiceAccountPermissionMap
from grouper.models.user import User
from grouper.repositories.interfaces import PermissionGrantRepository

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.entities.pagination import Pagination
    from grouper.models.base.session import Session
    from typing import Dict, Iterable, List, Optional


class GraphPermissionGrantRepository(PermissionGrantRepository):
    """Graph-aware storage layer for permission grants."""

    def __init__(self, graph, repository):
        # type: (GroupGraph, PermissionGrantRepository) -> None
        self.graph = graph
        self.repository = repository

    def all_grants(self):
        # type: () -> Dict[str, UniqueGrantsOfPermission]
        return self.graph.all_grants()

    def all_grants_of_permission(self, permission):
        # type: (str) -> UniqueGrantsOfPermission
        return self.graph.all_grants_of_permission(permission)

    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        self.repository.grant_permission_to_group(permission, argument, group)

    def grant_permission_to_service_account(self, permission, argument, service):
        # type: (str, str, str) -> None
        self.repository.grant_permission_to_service_account(permission, argument, service)

    def group_grants_for_permission(self, name, include_disabled_groups=False, argument=None):
        # type: (str, bool, Optional[str]) -> List[GroupPermissionGrant]
        return self.repository.group_grants_for_permission(name, include_disabled_groups, argument)

    def group_paginated_grants_for_permission(
        self,
        name,  # type: str
        pagination,  # type: Pagination[PermissionGroupGrantSortKey]
        include_disabled_groups=False,  # type: bool
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> PaginatedList[GroupPermissionGrant]
        grants = self.repository.group_grants_for_permission(
            name, include_disabled_groups, argument
        )

        if pagination.sort_key != PermissionGroupGrantSortKey.NONE:
            grants = sorted(
                grants,
                key=lambda p: getattr(p, pagination.sort_key.name.lower()),
                reverse=pagination.reverse_sort,
            )

        # Find the total length and then optionally slice.
        total = len(grants)
        if pagination.limit:
            grants = grants[pagination.offset : pagination.offset + pagination.limit]
        elif pagination.offset > 0:
            grants = grants[pagination.offset :]

        # Convert to the correct data transfer object and return.
        return PaginatedList[GroupPermissionGrant](
            values=grants, total=total, offset=pagination.offset, limit=pagination.limit
        )

    def permission_grants_for_group(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        group_details = self.graph.get_group_details(name)
        permissions = []
        for permission_data in group_details["permissions"]:
            permission = GroupPermissionGrant(
                group=name,
                permission=permission_data["permission"],
                argument=permission_data["argument"],
                granted_on=datetime.utcfromtimestamp(permission_data["granted_on"]),
                is_alias=permission_data["alias"],
            )
            permissions.append(permission)
        return permissions

    def permission_grants_for_service_account(self, name):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        """Return all permission grants for a service account.

        TODO(rra): Currently does not expand permission aliases because they are not expanded by
        the graph.
        """
        user_details = self.graph.get_user_details(name)
        permissions = []
        for permission_data in user_details["permissions"]:
            permission = ServiceAccountPermissionGrant(
                service_account=name,
                permission=permission_data["permission"],
                argument=permission_data["argument"],
                granted_on=datetime.utcfromtimestamp(permission_data["granted_on"]),
                is_alias=False,
            )
            permissions.append(permission)
        return permissions

    def permission_grants_for_user(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        user_details = self.graph.get_user_details(name)
        permissions = []
        for permission_data in user_details["permissions"]:
            permission = GroupPermissionGrant(
                group=permission_data["path"][-1],
                permission=permission_data["permission"],
                argument=permission_data["argument"],
                granted_on=datetime.utcfromtimestamp(permission_data["granted_on"]),
                is_alias=permission_data["alias"],
            )
            permissions.append(permission)
        return permissions

    def revoke_all_group_grants(self, permission):
        # type: (str) -> List[GroupPermissionGrant]
        return self.repository.revoke_all_group_grants(permission)

    def revoke_all_service_account_grants(self, permission):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        return self.repository.revoke_all_service_account_grants(permission)

    def service_account_grants_for_permission(self, name, argument=None):
        # type: (str, Optional[str]) -> List[ServiceAccountPermissionGrant]
        grants = self.repository.service_account_grants_for_permission(name, argument)
        return grants

    def service_account_paginated_grants_for_permission(
        self,
        name,  # type: str
        pagination,  # type: Pagination[PermissionServiceAccountGrantSortKey]
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> PaginatedList[ServiceAccountPermissionGrant]
        grants = self.repository.service_account_grants_for_permission(name, argument)

        if pagination.sort_key != PermissionServiceAccountGrantSortKey.NONE:
            grants = sorted(
                grants,
                key=lambda p: getattr(p, pagination.sort_key.name.lower()),
                reverse=pagination.reverse_sort,
            )

        # Find the total length and then optionally slice.
        total = len(grants)
        if pagination.limit:
            grants = grants[pagination.offset : pagination.offset + pagination.limit]
        elif pagination.offset > 0:
            grants = grants[pagination.offset :]

        # Convert to the correct data transfer object and return.
        return PaginatedList[ServiceAccountPermissionGrant](
            values=grants, total=total, offset=pagination.offset, limit=pagination.limit
        )

    def service_account_has_permission(self, service, permission):
        # type: (str, str) -> bool
        for grant in self.permission_grants_for_service_account(service):
            if permission == grant.permission:
                return True
        return False

    def user_has_permission(self, user, permission):
        # type: (str, str) -> bool
        for grant in self.permission_grants_for_user(user):
            if permission == grant.permission:
                return True
        return False


class SQLPermissionGrantRepository(PermissionGrantRepository):
    """SQL storage layer for permission grants."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def all_grants(self):
        # type: () -> Dict[str, UniqueGrantsOfPermission]
        raise NotImplementedError()

    def all_grants_of_permission(self, permission):
        # type: (str) -> UniqueGrantsOfPermission
        raise NotImplementedError()

    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        sql_group = Group.get(self.session, name=group)
        if not sql_group:
            raise GroupNotFoundException(group)
        sql_permission = Permission.get(self.session, name=permission)
        if not sql_permission:
            raise PermissionNotFoundException(permission)

        mapping = PermissionMap(
            permission_id=sql_permission.id, group_id=sql_group.id, argument=argument
        )
        mapping.add(self.session)

    def grant_permission_to_service_account(self, permission, argument, service):
        # type: (str, str, str) -> None
        sql_service = ServiceAccount.get(self.session, name=service)
        if not sql_service or not sql_service.user.enabled:
            raise ServiceAccountNotFoundException(service)
        sql_permission = Permission.get(self.session, name=permission)
        if not sql_permission:
            raise PermissionNotFoundException(permission)

        mapping = ServiceAccountPermissionMap(
            permission_id=sql_permission.id, service_account_id=sql_service.id, argument=argument
        )
        mapping.add(self.session)

    def group_grants_for_permission(self, name, include_disabled_groups=False, argument=None):
        # type: (str, bool, Optional[str]) -> List[GroupPermissionGrant]
        permission = Permission.get(self.session, name=name)
        if not permission or not permission.enabled:
            return []
        grants = (
            self.session.query(
                Group.groupname, PermissionMap.argument, PermissionMap.id, PermissionMap.granted_on
            )
            .filter(
                PermissionMap.permission_id == permission.id, Group.id == PermissionMap.group_id
            )
            .order_by(Group.groupname, PermissionMap.argument)
        )
        if not include_disabled_groups:
            grants = grants.filter(Group.enabled == True)

        if argument:
            grants = grants.filter(PermissionMap.argument == argument)

        return [
            GroupPermissionGrant(
                group=g.groupname,
                permission=name,
                argument=g.argument,
                granted_on=g.granted_on,
                is_alias=False,
                grant_id=g.id,
            )
            for g in grants.all()
        ]

    def permission_grants_for_group(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        """Return all permission grants a group has.

        TODO(rra): Currently does not expand permission aliases, and therefore doesn't match the
        graph behavior.  Use with caution until that is fixed.
        """
        group = Group.get(self.session, name=name)
        if not group or not group.enabled:
            return []
        return self._permission_grants_for_group_ids([group.id])

    def permission_grants_for_service_account(self, name):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        """Return all permission grants for a service account.

        TODO(rra): Currently does not expand permission aliases.
        """
        grants = self.session.query(
            Permission.name,
            ServiceAccountPermissionMap.argument,
            ServiceAccountPermissionMap.granted_on,
            ServiceAccountPermissionMap.id,
        ).filter(
            User.username == name,
            User.enabled == True,
            ServiceAccount.user_id == User.id,
            Permission.id == ServiceAccountPermissionMap.permission_id,
            ServiceAccountPermissionMap.service_account_id == ServiceAccount.id,
        )
        return [
            ServiceAccountPermissionGrant(
                service_account=name,
                permission=g.name,
                argument=g.argument,
                granted_on=g.granted_on,
                is_alias=False,
                grant_id=g.id,
            )
            for g in grants.all()
        ]

    def permission_grants_for_user(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        """Return all permission grants a user has from whatever source.

        TODO(rra): Currently does not expand permission aliases, and therefore doesn't match the
        graph behavior.  Use with caution until that is fixed.
        """
        now = datetime.utcnow()
        user = User.get(self.session, name=name)
        if not user or user.role_user or user.is_service_account or not user.enabled:
            return []

        # Get the groups of which this user is a direct member.
        groups = (
            self.session.query(Group.id)
            .join(GroupEdge, Group.id == GroupEdge.group_id)
            .join(User, User.id == GroupEdge.member_pk)
            .filter(
                Group.enabled == True,
                User.id == user.id,
                GroupEdge.active == True,
                GroupEdge.member_type == OBJ_TYPES["User"],
                GroupEdge._role != GROUP_EDGE_ROLES.index("np-owner"),
                or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
            )
            .distinct()
        )
        group_ids = [g.id for g in groups]

        # If the user was not a member of any group, we can return early.
        if not group_ids:
            return []

        # Now, return all the permission grants for those groups.
        return self._permission_grants_for_group_ids(group_ids)

    def revoke_all_group_grants(self, permission):
        # type: (str) -> List[GroupPermissionGrant]
        sql_permission = Permission.get(self.session, name=permission)
        if not sql_permission:
            return []
        grants = (
            self.session.query(
                PermissionMap.id, Group.groupname, PermissionMap.argument, PermissionMap.granted_on
            )
            .filter(
                Group.id == PermissionMap.group_id,
                PermissionMap.permission_id == sql_permission.id,
            )
            .all()
        )
        ids = [g.id for g in grants]
        self.session.query(PermissionMap).filter(PermissionMap.id.in_(ids)).delete(
            synchronize_session="fetch"
        )
        return [
            GroupPermissionGrant(
                group=g.groupname,
                permission=permission,
                argument=g.argument,
                granted_on=g.granted_on,
                is_alias=False,
                grant_id=g.id,
            )
            for g in grants
        ]

    def revoke_all_service_account_grants(self, permission):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        sql_permission = Permission.get(self.session, name=permission)
        if not sql_permission:
            return []
        grants = (
            self.session.query(
                ServiceAccountPermissionMap.id,
                User.username,
                ServiceAccountPermissionMap.argument,
                ServiceAccountPermissionMap.granted_on,
            )
            .filter(
                User.id == ServiceAccount.user_id,
                ServiceAccount.id == ServiceAccountPermissionMap.service_account_id,
                PermissionMap.permission_id == sql_permission.id,
            )
            .all()
        )
        ids = [g.id for g in grants]
        self.session.query(ServiceAccountPermissionMap).filter(
            ServiceAccountPermissionMap.id.in_(ids)
        ).delete(synchronize_session="fetch")
        return [
            ServiceAccountPermissionGrant(
                service_account=g.username,
                permission=permission,
                argument=g.argument,
                granted_on=g.granted_on,
                is_alias=False,
                grant_id=g.id,
            )
            for g in grants
        ]

    def service_account_grants_for_permission(self, name, argument=None):
        # type: (str, Optional[str]) -> List[ServiceAccountPermissionGrant]
        permission = Permission.get(self.session, name=name)
        if not permission or not permission.enabled:
            return []
        grants = (
            self.session.query(
                User.username,
                ServiceAccountPermissionMap.argument,
                ServiceAccountPermissionMap.granted_on,
                ServiceAccountPermissionMap.id,
            )
            .filter(
                ServiceAccountPermissionMap.permission_id == permission.id,
                ServiceAccount.id == ServiceAccountPermissionMap.service_account_id,
                User.id == ServiceAccount.user_id,
            )
            .order_by(User.username, ServiceAccountPermissionMap.argument)
        )

        if argument:
            grants = grants.filter(ServiceAccountPermissionMap.argument == argument)

        return [
            ServiceAccountPermissionGrant(
                service_account=g.username,
                permission=name,
                argument=g.argument,
                granted_on=g.granted_on,
                is_alias=False,
                grant_id=g.id,
            )
            for g in grants.all()
        ]

    def service_account_has_permission(self, service, permission):
        # type: (str, str) -> bool
        for grant in self.permission_grants_for_service_account(service):
            if permission == grant.permission:
                return True
        return False

    def user_has_permission(self, user, permission):
        # type: (str, str) -> bool
        for grant in self.permission_grants_for_user(user):
            if permission == grant.permission:
                return True
        return False

    def _permission_grants_for_group_ids(self, group_ids):
        # type: (Iterable[int]) -> List[GroupPermissionGrant]
        """Given a set of group IDs, return all direct or inherited permission grants.

        Used to build the full list of permission grants for a set of groups, taking inheritance
        into account.  Shared code between permission_grants_for_user and
        permission_grants_for_group.

        TODO(rra): Currently does not expand permission aliases, and therefore doesn't match the
        graph behavior.
        """
        # Get the parent groups of the initial groups, repeating until we run out of levels of the
        # tree.  Use a set of seen group_ids to avoid querying the same group twice if a user is a
        # member of it via multiple paths.
        now = datetime.utcnow()
        seen_group_ids = set(group_ids)
        while group_ids:
            parent_groups = (
                self.session.query(Group.id)
                .join(GroupEdge, Group.id == GroupEdge.group_id)
                .filter(
                    GroupEdge.member_pk.in_(group_ids),
                    Group.enabled == True,
                    GroupEdge.active == True,
                    GroupEdge.member_type == OBJ_TYPES["Group"],
                    GroupEdge._role != GROUP_EDGE_ROLES.index("np-owner"),
                    or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
                )
                .distinct()
            )
            group_ids = [g.id for g in parent_groups if g.id not in seen_group_ids]
            seen_group_ids.update(group_ids)

        # Return the permission grants.
        group_permission_grants = (
            self.session.query(
                Group.groupname,
                Permission.name,
                PermissionMap.argument,
                PermissionMap.granted_on,
                PermissionMap.id,
            )
            .filter(
                Permission.id == PermissionMap.permission_id,
                PermissionMap.group_id.in_(seen_group_ids),
                Group.id == PermissionMap.group_id,
            )
            .all()
        )
        return [
            GroupPermissionGrant(
                group=g.groupname,
                permission=g.name,
                argument=g.argument,
                granted_on=g.granted_on,
                is_alias=False,
                grant_id=g.id,
            )
            for g in group_permission_grants
        ]

    def group_paginated_grants_for_permission(
        self,
        name,  # type: str
        pagination,  # type: Pagination[PermissionGroupGrantSortKey]
        include_disabled_groups=False,  # type: bool
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> PaginatedList[GroupPermissionGrant]
        raise NotImplementedError()

    def service_account_paginated_grants_for_permission(
        self,
        name,  # type: str
        pagination,  # type: Pagination[PermissionServiceAccountGrantSortKey]
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> PaginatedList[ServiceAccountPermissionGrant]
        raise NotImplementedError()
