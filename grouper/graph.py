import logging
from collections import defaultdict
from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING

from networkx import DiGraph, single_source_shortest_path
from sqlalchemy import or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql import label, literal

from grouper.entities.group import Group, GroupJoinPolicy
from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.entities.permission import Permission
from grouper.entities.permission_grant import GroupPermissionGrant, UniqueGrantsOfPermission
from grouper.entities.user import PublicKey, User, UserMetadata
from grouper.models.counter import Counter
from grouper.models.group import Group as SQLGroup
from grouper.models.group_edge import GroupEdge
from grouper.models.group_service_accounts import GroupServiceAccount
from grouper.models.permission import Permission as SQLPermission
from grouper.models.permission_map import PermissionMap
from grouper.models.public_key import PublicKey as SQLPublicKey
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User as SQLUser
from grouper.models.user_metadata import UserMetadata as SQLUserMetadata
from grouper.models.user_password import UserPassword
from grouper.plugin import get_plugin_proxy
from grouper.service_account import all_service_account_permissions
from grouper.util import singleton

if TYPE_CHECKING:
    from grouper.entities.permission_grant import ServiceAccountPermissionGrant
    from grouper.models.base.session import Session
    from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

    Node = Tuple[str, str]
    Edge = Tuple[Node, Node, Dict[str, int]]

MEMBER_TYPE_MAP = {"User": "users", "Group": "subgroups"}
EPOCH = datetime(1970, 1, 1)


@singleton
def Graph():
    # type: () -> GroupGraph
    return GroupGraph()


# Raise these exceptions when asking about users or groups that are not cached.
class NoSuchUser(Exception):
    pass


class NoSuchGroup(Exception):
    pass


class GroupGraph:
    """The cached permission graph.

    The graph is internally represented by four major components: the users, groups, and
    permissions dictionaries, which map names of those objects to named tuples (or, in the case of
    users, dictionaries for now) containing the metadata for those objects; the
    group_service_accounts dictionary that maps group names to the service accounts that group
    owns; the group_grants and service_account_grants dictionaries that map groups and service
    accounts to the permission grants they have, and the internal graph and rgraph directed graphs.

    The cached user metadata includes metadata for disabled users, and the disabled_groups internal
    attribute holds a dictionary of group names to Group named tuples for disabled groups.  Other
    than those exceptions, stored graph metadata includes only enabled objects.

    The directed graphs are used to calculate inherited membership and permissions.  _graph is a
    directed graph with all users and groups as nodes, and with directed edges from groups to their
    members (whether users or other groups).  _rgraph is the same graph reversed, so the edges
    point from users and groups to the groups of which they are a member.

    Finally, disabled_groups is a sorted list of Group named tuples for all disabled groups.

    Attributes:
        lock: Read lock on the data
        checkpoint: Revision of Grouper data
        checkpoint_time: Last update time of Grouper data
        users: Names of all enabled users
        groups: Names of all enabled groups
        permissions: Names of all enabled permissions
        user_metadata: Full information about each user
    """

    def __init__(self):
        # type: () -> None
        self._logger = logging.getLogger(__name__)

        # lock is a read lock to ensure consistency while iterating through data.  update_lock is
        # the write lock, held to prevent two updates from the database from running at the same
        # time.  lock has to be public for now because some API code takes the lock and looks at
        # data elements directly.  :(
        self.lock = RLock()
        self._update_lock = RLock()

        # Initialized by update_from_db.
        self._graph = DiGraph()
        self._rgraph = DiGraph()

        # The last update sequence number and timestamp of the database underlying the graph.
        self.checkpoint = 0
        self.checkpoint_time = 0

        # Collection of all groups and permissions.
        self._groups = {}  # type: Dict[str, Group]
        self._disabled_groups = {}  # type: Dict[str, Group]
        self._permissions = {}  # type: Dict[str, Permission]

        # Collection of all users and their data.  For now, this is represented as a dict rather
        # than as a data transfer object.  Users have a lot of structure, so require a more
        # complicated object, which hasn't been written yet.
        self.user_metadata = {}  # type: Dict[str, Dict[str, Any]]

        # Map of groups to their permission grants.
        self._group_grants = {}  # type: Dict[str, List[GroupPermissionGrant]]

        # Map of permissions to users and service accounts with that grant.
        self._grants_by_permission = {}  # type: Dict[str, UniqueGrantsOfPermission]

        # Map of groups to the service accounts they own, and from service accounts to their
        # permission grants.
        self._group_service_accounts = {}  # type: Dict[str, List[str]]
        self._service_account_grants = {}  # type: Dict[str, List[ServiceAccountPermissionGrant]]

    @classmethod
    def from_db(cls, session):
        # type: (Session) -> GroupGraph
        inst = cls()
        inst.update_from_db(session)
        return inst

    @property
    def groups(self):
        # type: () -> List[str]
        with self.lock:
            return list(self._groups.keys())

    @property
    def permissions(self):
        # type: () -> List[str]
        with self.lock:
            return list(self._permissions.keys())

    @property
    def users(self):
        # type: () -> List[str]
        with self.lock:
            return [u for u, d in self.user_metadata.items() if d["enabled"]]

    def update_from_db(self, session):
        # type: (Session) -> None
        # Only allow one thread at a time to construct a fresh graph.
        with self._update_lock:
            checkpoint, checkpoint_time = self._get_checkpoint(session)
            if checkpoint == self.checkpoint:
                self._logger.debug("Checkpoint hasn't changed. Not Updating.")
                return
            self._logger.debug("Checkpoint changed; updating!")

            start_time = datetime.utcnow()

            user_metadata = self._get_user_metadata(session)
            groups, disabled_groups = self._get_groups(session, user_metadata)
            permissions = self._get_permissions(session)
            group_grants = self._get_group_grants(session)
            group_service_accounts = self._get_group_service_accounts(session)
            service_account_grants = all_service_account_permissions(session)

            nodes = self._get_nodes(groups, user_metadata)
            edges = self._get_edges(session)
            edges_without_np_owner = [
                (n1, n2) for n1, n2, r in edges if GROUP_EDGE_ROLES[r["role"]] != "np-owner"
            ]

            graph = DiGraph()
            graph.add_nodes_from(nodes)
            graph.add_edges_from(edges)
            rgraph = graph.reverse()

            # We need a separate graph without np-owner edges to construct the mapping of
            # permissions to users with that grant.
            permission_graph = DiGraph()
            permission_graph.add_nodes_from(nodes)
            permission_graph.add_edges_from(edges_without_np_owner)
            grants_by_permission = self._get_grants_by_permission(
                permission_graph, group_grants, service_account_grants, user_metadata
            )

            with self.lock:
                self._graph = graph
                self._rgraph = rgraph
                self.checkpoint = checkpoint
                self.checkpoint_time = checkpoint_time
                self.user_metadata = user_metadata
                self._groups = groups
                self._disabled_groups = disabled_groups
                self._permissions = permissions
                self._group_grants = group_grants
                self._group_service_accounts = group_service_accounts
                self._service_account_grants = service_account_grants
                self._grants_by_permission = grants_by_permission

            duration = datetime.utcnow() - start_time
            get_plugin_proxy().log_graph_update_duration(int(duration.total_seconds() * 1000))

    @staticmethod
    def _get_checkpoint(session):
        # type: (Session) -> Tuple[int, int]
        counter = session.query(Counter).filter_by(name="updates").scalar()
        if counter is None:
            return 0, 0
        return counter.count, int(counter.last_modified.strftime("%s"))

    @staticmethod
    def _get_user_metadata(session):
        # type: (Session) -> Dict[str, Any]
        """Returns a dict of username: { dict of metadata }."""

        def user_indexify(data):
            # type: (Iterable[Any]) -> Dict[int, List[Any]]
            ret = defaultdict(list)  # type: Dict[int, List[Any]]
            for item in data:
                ret[item.user_id].append(item)
            return ret

        passwords = user_indexify(session.query(UserPassword).all())
        public_keys = user_indexify(session.query(SQLPublicKey).all())
        user_metadata = user_indexify(session.query(SQLUserMetadata).all())

        service_account_data = (
            session.query(
                ServiceAccount.user_id,
                ServiceAccount.description,
                ServiceAccount.machine_set,
                label("owner", SQLGroup.groupname),
            )
            .outerjoin(
                GroupServiceAccount, ServiceAccount.id == GroupServiceAccount.service_account_id
            )
            .outerjoin(SQLGroup, GroupServiceAccount.group_id == SQLGroup.id)
        )
        service_accounts = {r.user_id: r for r in service_account_data}

        users = session.query(SQLUser)

        out = {}
        for user in users:
            out[user.username] = {
                "enabled": user.enabled,
                "role_user": user.role_user,
                "passwords": [
                    {
                        "name": password.name,
                        "hash": password.password_hash,
                        "salt": password.salt,
                        "func": "crypt(3)-$6$",
                    }
                    for password in passwords.get(user.id, [])
                ],
                "public_keys": [
                    {
                        "public_key": key.public_key,
                        "fingerprint": key.fingerprint,
                        "fingerprint_sha256": key.fingerprint_sha256,
                        "created_on": str(key.created_on),
                        "id": key.id,
                    }
                    for key in public_keys.get(user.id, [])
                ],
                "metadata": [
                    {
                        "data_key": row.data_key,
                        "data_value": row.data_value,
                        "last_modified": str(row.last_modified),
                    }
                    for row in user_metadata.get(user.id, [])
                ],
            }
            if user.is_service_account:
                if user.id in service_accounts:
                    account = service_accounts[user.id]
                    out[user.username]["service_account"] = {
                        "description": account.description,
                        "machine_set": account.machine_set,
                    }
                    if account.owner:
                        out[user.username]["service_account"]["owner"] = account.owner
                else:
                    logging.error(
                        "User %s marked as service account but has no service account row",
                        user.username,
                    )
        return out

    @staticmethod
    def _get_group_grants(session):
        # type: (Session) -> Dict[str, List[GroupPermissionGrant]]
        """Returns a dict of group names to lists of permission grants."""
        permissions = session.query(SQLPermission, PermissionMap, SQLGroup.groupname).filter(
            SQLPermission.id == PermissionMap.permission_id,
            PermissionMap.group_id == SQLGroup.id,
            SQLGroup.enabled == True,
        )

        out = defaultdict(list)  # type: Dict[str, List[GroupPermissionGrant]]
        for (permission, permission_map, groupname) in permissions:
            out[groupname].append(
                GroupPermissionGrant(
                    group=groupname,
                    permission=permission.name,
                    argument=permission_map.argument,
                    granted_on=permission_map.granted_on,
                    is_alias=False,
                    grant_id=permission_map.id,
                )
            )

            aliases = get_plugin_proxy().get_aliases_for_mapped_permission(
                session, permission.name, permission_map.argument
            )

            for (name, arg) in aliases:
                out[groupname].append(
                    GroupPermissionGrant(
                        group=groupname,
                        permission=name,
                        argument=arg,
                        granted_on=permission_map.granted_on,
                        is_alias=True,
                    )
                )

        return out

    @staticmethod
    def _get_permissions(session):
        # type: (Session) -> Dict[str, Permission]
        """Returns all permissions in the graph."""
        permissions = session.query(SQLPermission).filter(SQLPermission.enabled == True)
        out = {}
        for permission in permissions:
            out[permission.name] = Permission(
                name=permission.name,
                description=permission.description,
                created_on=permission.created_on,
                audited=permission.audited,
                enabled=permission.enabled,
            )
        return out

    @staticmethod
    def _get_groups(session, user_metadata):
        # type: (Session, Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Group], Dict[str, Group]]
        sql_groups = session.query(SQLGroup)
        groups = {}  # type: Dict[str, Group]
        disabled_groups = {}  # type: Dict[str, Group]
        for sql_group in sql_groups:
            if sql_group.groupname in user_metadata:
                is_role_user = user_metadata[sql_group.groupname]["role_user"]
            else:
                is_role_user = False
            group = Group(
                name=sql_group.groupname,
                description=sql_group.description,
                email_address=sql_group.email_address,
                join_policy=GroupJoinPolicy(sql_group.canjoin),
                enabled=sql_group.enabled,
                is_role_user=is_role_user,
            )
            if group.enabled:
                groups[group.name] = group
            else:
                disabled_groups[group.name] = group
        return groups, disabled_groups

    @staticmethod
    def _get_group_service_accounts(session):
        # type: (Session) -> Dict[str, List[str]]
        """Returns a dict of groupname: { list of service account names }."""
        out = defaultdict(list)  # type: Dict[str, List[str]]
        tuples = session.query(SQLGroup.groupname, SQLUser.username).filter(
            GroupServiceAccount.group_id == SQLGroup.id,
            GroupServiceAccount.service_account_id == ServiceAccount.id,
            ServiceAccount.user_id == SQLUser.id,
        )
        for group, account in tuples:
            out[group].append(account)
        return out

    @staticmethod
    def _get_nodes(groups, user_metadata):
        # type: (Dict[str, Group], Dict[str, Dict[str, Any]]) -> List[Node]
        return [("User", u) for u in user_metadata.keys()] + [("Group", g) for g in groups]

    @staticmethod
    def _get_edges(session):
        # type: (Session) -> List[Edge]
        parent = aliased(SQLGroup)
        group_member = aliased(SQLGroup)
        user_member = aliased(SQLUser)

        now = datetime.utcnow()

        query = (
            session.query(
                label("groupname", parent.groupname),
                label("type", literal("Group")),
                label("name", group_member.groupname),
                label("role", GroupEdge._role),
                label("expiration", GroupEdge.expiration),
            )
            .filter(
                parent.id == GroupEdge.group_id,
                group_member.id == GroupEdge.member_pk,
                GroupEdge.active == True,
                parent.enabled == True,
                group_member.enabled == True,
                or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
                GroupEdge.member_type == 1,
            )
            .union(
                session.query(
                    label("groupname", parent.groupname),
                    label("type", literal("User")),
                    label("name", user_member.username),
                    label("role", GroupEdge._role),
                    label("expiration", GroupEdge.expiration),
                ).filter(
                    parent.id == GroupEdge.group_id,
                    user_member.id == GroupEdge.member_pk,
                    GroupEdge.active == True,
                    parent.enabled == True,
                    user_member.enabled == True,
                    or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
                    GroupEdge.member_type == 0,
                )
            )
        )

        edges = []
        for record in query.all():
            edges.append(
                (
                    ("Group", record.groupname),
                    (record.type, record.name),
                    {"role": record.role, "expiration": record.expiration},
                )
            )

        return edges

    @staticmethod
    def _get_grants_by_permission(
        permission_graph,  # type: DiGraph
        group_grants,  # type: Dict[str, List[GroupPermissionGrant]]
        service_account_grants,  # type: Dict[str, List[ServiceAccountPermissionGrant]]
        user_metadata,  # type: Dict[str, Any]
    ):
        # type: (...) -> Dict[str, UniqueGrantsOfPermission]
        """Build a map of permissions to users and service accounts with grants."""
        service_grants = defaultdict(
            lambda: defaultdict(set)
        )  # type: Dict[str, Dict[str, Set[str]]]
        for account, service_grant_list in service_account_grants.items():
            for service_grant in service_grant_list:
                service_grants[service_grant.permission][account].add(service_grant.argument)

        # For each group that has a permission grant, determine all of its users from the graph,
        # and then record each permission grant of that group as a grant to all of those users.
        # Use a set for the arguments in our intermediate data structure to handle uniqueness.  We
        # have to separate role users from non-role users here, since they're otherwise identical
        # and are both handled by the same graph.
        #
        # TODO(rra): We currently have a bug that erroneously allows service accounts to be added
        # as regular members of groups, causing them to show up in the user graph.  Work around
        # this by skipping such users based on user metadata.  This special-case can be removed
        # once we enforce that the user underlying service accounts cannot be added as a member of
        # groups.  (A better place to put this is to remove service accounts from the nodes in the
        # graph, but this will break some arguably broken software that (ab)used the membership of
        # service accounts in groups, so we'll do that later when we fix that bug.)
        role_user_grants = defaultdict(
            lambda: defaultdict(set)
        )  # type: Dict[str, Dict[str, Set[str]]]
        user_grants = defaultdict(lambda: defaultdict(set))  # type: Dict[str, Dict[str, Set[str]]]
        for group, grant_list in group_grants.items():
            members = set()  # type: Set[str]
            paths = single_source_shortest_path(permission_graph, ("Group", group))
            for member, path in paths.items():
                member_type, member_name = member
                if member_type != "User":
                    continue
                if "service_account" in user_metadata[member_name]:
                    continue
                members.add(member_name)
            for grant in grant_list:
                for member in members:
                    if user_metadata[member]["role_user"]:
                        role_user_grants[grant.permission][member].add(grant.argument)
                    else:
                        user_grants[grant.permission][member].add(grant.argument)

        # Now, assemble the service_grants, role_user_grants, and user_grants dicts into a single
        # dictionary of permission names to UniqueGrantsOfPermission named tuples.  defaultdicts
        # don't compare easily to dicts and the API server wants to return lists, so convert to a
        # regular dict with list values for ease of testing.  (The performance loss should be
        # insignificant.)
        all_grants = {}  # type: Dict[str, UniqueGrantsOfPermission]
        for permission in set(user_grants.keys()) | set(service_grants.keys()):
            grants = UniqueGrantsOfPermission(
                users={k: sorted(v) for k, v in user_grants[permission].items()},
                role_users={k: sorted(v) for k, v in role_user_grants[permission].items()},
                service_accounts={k: sorted(v) for k, v in service_grants[permission].items()},
            )
            all_grants[permission] = grants

        return all_grants

    def all_grants(self):
        # type: () -> Dict[str, UniqueGrantsOfPermission]
        return self._grants_by_permission

    def all_grants_of_permission(self, permission):
        # type: (str) -> UniqueGrantsOfPermission
        empty_grants = UniqueGrantsOfPermission(users={}, role_users={}, service_accounts={})
        return self._grants_by_permission.get(permission, empty_grants)

    def all_user_metadata(self):
        # type: () -> Dict[str, User]
        users = {}  # type: Dict[str, User]
        with self.lock:
            for user, data in self.user_metadata.items():
                if not data["enabled"]:
                    continue
                if "service_account" in data:
                    continue
                metadata = [UserMetadata(m["data_key"], m["data_value"]) for m in data["metadata"]]
                public_keys = [
                    PublicKey(k["public_key"], k["fingerprint"], k["fingerprint_sha256"])
                    for k in data["public_keys"]
                ]
                users[user] = User(
                    name=user,
                    enabled=data["enabled"],
                    role_user=data["role_user"],
                    metadata=metadata,
                    public_keys=public_keys,
                )
        return users

    def get_permissions(self, audited=False):
        # type: (bool) -> List[Permission]
        """Get the list of permissions as Permission instances."""
        with self.lock:
            if audited:
                permissions = [p for p in self._permissions.values() if p.audited]
            else:
                permissions = list(self._permissions.values())
        return sorted(permissions, key=lambda p: p.name)

    def get_permission_details(self, name, expose_aliases=True):
        # type: (str, bool) -> Dict[str, Union[bool, Dict[str, Any]]]
        """ Get a permission and what groups and service accounts it's assigned to. """
        with self.lock:
            data = {
                "groups": {},
                "service_accounts": {},
            }  # type: Dict[str, Dict[str, Any]]

            # Get all mapped versions of the permission. This is only direct relationships.
            direct_groups = set()
            for groupname, grants in self._group_grants.items():
                for grant in grants:
                    if grant.permission == name:
                        data["groups"][groupname] = self.get_group_details(
                            groupname, show_permission=name, expose_aliases=expose_aliases
                        )
                        direct_groups.add(groupname)
                        break

            # Now find all members of these groups going down the tree.
            checked_groups = set()  # type: Set[str]
            for groupname in direct_groups:
                group = ("Group", groupname)
                paths = single_source_shortest_path(self._graph, group, None)
                for member, path in paths.items():
                    if member == group:
                        continue
                    member_type, member_name = member
                    if member_type != "Group":
                        continue
                    if member_name in checked_groups:
                        continue
                    checked_groups.add(member_name)
                    data["groups"][member_name] = self.get_group_details(
                        member_name, show_permission=name, expose_aliases=expose_aliases
                    )

            # Finally, add all service accounts.
            for account, service_grants in self._service_account_grants.items():
                for service_grant in service_grants:
                    if service_grant.permission == name:
                        details = {
                            "permission": service_grant.permission,
                            "argument": service_grant.argument,
                            "granted_on": (service_grant.granted_on - EPOCH).total_seconds(),
                        }
                        if account in data["service_accounts"]:
                            data["service_accounts"][account]["permissions"].append(details)
                        else:
                            data["service_accounts"][account] = {"permissions": [details]}

            # Add permission audit value
            permission_audited = {"audited": self._permissions[name].audited}
            return {**data, **permission_audited}

    def get_disabled_groups(self):
        # type: () -> List[Group]
        """ Get the list of disabled groups as Group instances sorted by groupname. """
        with self.lock:
            return sorted(self._disabled_groups.values(), key=lambda g: g.name)

    def get_groups(self, audited=False, directly_audited=False):
        # type: (bool, bool) -> List[Group]
        """Get the list of groups as Group instances sorted by group name.

        Arg(s):
            audited (bool): true to get only audited groups
            directly_audited (bool): true to get only directly audited
                groups (implies `audited` is true)
        """
        if directly_audited:
            audited = True
        with self.lock:
            groups = sorted(self._groups.values(), key=lambda g: g.name)
            if audited:

                def is_directly_audited(group):
                    # type: (Group) -> bool
                    for grant in self._group_grants[group.name]:
                        if self._permissions[grant.permission].audited:
                            return True
                    return False

                directly_audited_groups = list(filter(is_directly_audited, groups))
                if directly_audited:
                    return directly_audited_groups
                queue = [("Group", group.name) for group in directly_audited_groups]
                audited_group_nodes = set()  # type: Set[Node]
                while len(queue):
                    g = queue.pop()
                    if g not in audited_group_nodes:
                        audited_group_nodes.add(g)
                        for nhbr in self._graph.neighbors(g):  # Members of g.
                            if nhbr[0] == "Group":
                                queue.append(nhbr)
                groups = sorted(
                    [self._groups[group[1]] for group in audited_group_nodes], key=lambda g: g.name
                )
        return groups

    def get_group_details(self, groupname, show_permission=None, expose_aliases=True):
        # type: (str, Optional[str], bool) -> Dict[str, Any]
        """Get users and permissions that belong to a group. Raise NoSuchGroup
        for missing groups."""

        with self.lock:
            data = {
                "group": {"name": groupname},
                "users": {},
                "groups": {},
                "subgroups": {},
                "permissions": [],
            }  # type: Dict[str, Any]
            if groupname in self._group_service_accounts:
                data["service_accounts"] = self._group_service_accounts[groupname]
            if groupname in self._groups and self._groups[groupname].email_address:
                data["group"]["contacts"] = {"email": self._groups[groupname].email_address}

            # This is calculated based on all the permissions that apply to this group. Since this
            # is a graph walk, we calculate it here when we're getting this data.
            group_audited = False

            group = ("Group", groupname)
            if not self._graph.has_node(group):
                raise NoSuchGroup("Group %s is either missing or disabled." % groupname)
            paths = single_source_shortest_path(self._graph, group)
            rpaths = single_source_shortest_path(self._rgraph, group)

            for member, path in paths.items():
                if member == group:
                    continue
                member_type, member_name = member
                role = self._graph[group][path[1]]["role"]
                expiration = self._graph[group][path[1]]["expiration"]
                data[MEMBER_TYPE_MAP[member_type]][member_name] = {
                    "name": member_name,
                    "path": [elem[1] for elem in path],
                    "distance": len(path) - 1,
                    "role": role,
                    "rolename": GROUP_EDGE_ROLES[role],
                    "expiration": str(expiration),
                }

            for parent, path in rpaths.items():
                if parent == group:
                    continue
                _, parent_name = parent
                role = self._rgraph[path[-2]][parent]["role"]
                data["groups"][parent_name] = {
                    "name": parent_name,
                    "path": [elem[1] for elem in path],
                    "distance": len(path) - 1,
                    "role": role,
                    "rolename": GROUP_EDGE_ROLES[role],
                }
                for grant in self._group_grants.get(parent_name, []):
                    if show_permission is not None and grant.permission != show_permission:
                        continue
                    if self._permissions[grant.permission].audited:
                        group_audited = True
                        perm_audited = True
                    else:
                        perm_audited = False

                    perm_data = {
                        "permission": grant.permission,
                        "argument": grant.argument,
                        "granted_on": (grant.granted_on - EPOCH).total_seconds(),
                        "distance": len(path) - 1,
                        "path": [elem[1] for elem in path],
                        "audited": perm_audited,
                    }

                    if expose_aliases:
                        perm_data["alias"] = grant.is_alias

                    data["permissions"].append(perm_data)

            for grant in self._group_grants.get(groupname, []):
                if show_permission is not None and grant.permission != show_permission:
                    continue
                if self._permissions[grant.permission].audited:
                    group_audited = True
                    perm_audited = True
                else:
                    perm_audited = False

                perm_data = {
                    "permission": grant.permission,
                    "argument": grant.argument,
                    "granted_on": (grant.granted_on - EPOCH).total_seconds(),
                    "distance": 0,
                    "path": [groupname],
                    "audited": perm_audited,
                }

                if expose_aliases:
                    perm_data["alias"] = grant.is_alias

                data["permissions"].append(perm_data)

            data["audited"] = group_audited
            return data

    def get_user_details(self, username, expose_aliases=True):
        # type: (str, bool) -> Dict[str, Any]
        """ Get a user's groups and permissions.  Raise NoSuchUser for missing users."""
        groups = {}  # type: Dict[str, Dict[str, Any]]
        permissions = []  # type: List[Dict[str, Any]]
        user_details = {"groups": groups, "permissions": permissions}

        with self.lock:
            if username not in self.user_metadata:
                raise NoSuchUser("User %s is either missing or disabled." % username)

            user = ("User", username)

            # For disabled users or users introduced between SQL queries, just
            # return empty details.
            if not self._rgraph.has_node(user):
                return user_details

            # If the user is a service account, its permissions are only those of the service
            # account and we don't do any graph walking.
            if "service_account" in self.user_metadata[username]:
                if username in self._service_account_grants:
                    for service_grant in self._service_account_grants[username]:
                        permissions.append(
                            {
                                "permission": service_grant.permission,
                                "argument": service_grant.argument,
                                "granted_on": (service_grant.granted_on - EPOCH).total_seconds(),
                            }
                        )
                return user_details

            # User permissions are inherited from all groups for which their
            # role is not "np-owner".  User groups are all groups in which a
            # user is a member by inheritance, except for ancestors of groups
            # where their role is "np-owner", unless the user is a member of
            # such an ancestor via a non-"np-owner" role in another group.
            rpaths = {}  # type: Dict[str, List[Tuple[str, str]]]
            for group in self._rgraph.neighbors(user):
                role = self._rgraph[user][group]["role"]
                if GROUP_EDGE_ROLES[role] == "np-owner":
                    group_name = group[1]
                    groups[group_name] = {
                        "name": group_name,
                        "path": [username, group_name],
                        "distance": 1,
                        "role": role,
                        "rolename": GROUP_EDGE_ROLES[role],
                    }
                    continue
                new_rpaths = single_source_shortest_path(self._rgraph, group)
                for parent, path in new_rpaths.items():
                    if parent not in rpaths or 1 + len(path) < len(rpaths[parent]):
                        rpaths[parent] = [user] + path

            for parent, path in rpaths.items():
                if parent == user:
                    continue
                _, parent_name = parent
                role = self._rgraph[path[-2]][parent]["role"]
                groups[parent_name] = {
                    "name": parent_name,
                    "path": [elem[1] for elem in path],
                    "distance": len(path) - 1,
                    "role": role,
                    "rolename": GROUP_EDGE_ROLES[role],
                }

                for grant in self._group_grants[parent_name]:
                    perm_data = {
                        "permission": grant.permission,
                        "argument": grant.argument,
                        "granted_on": (grant.granted_on - EPOCH).total_seconds(),
                        "path": [elem[1] for elem in path],
                        "distance": len(path) - 1,
                    }

                    if expose_aliases:
                        perm_data["alias"] = grant.is_alias

                    permissions.append(perm_data)

            return user_details
