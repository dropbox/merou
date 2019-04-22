import logging
from collections import defaultdict, namedtuple
from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING

from networkx import DiGraph, single_source_shortest_path
from six import iteritems, itervalues
from sqlalchemy import or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql import label, literal

from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.models.counter import Counter
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.group_service_accounts import GroupServiceAccount
from grouper.models.permission import MappedPermission, Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.public_key import PublicKey
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User
from grouper.models.user_metadata import UserMetadata
from grouper.models.user_password import UserPassword
from grouper.plugin import get_plugin_proxy
from grouper.role_user import is_role_user
from grouper.service_account import all_service_account_permissions
from grouper.util import singleton

if TYPE_CHECKING:
    from grouper.service_account import ServiceAccountPermission
    from typing import Any, Dict, List, Optional, Set

MEMBER_TYPE_MAP = {"User": "users", "Group": "subgroups"}
EPOCH = datetime(1970, 1, 1)


@singleton
def Graph():
    # type: () -> GroupGraph
    return GroupGraph()


# A GroupGraph caches users, permissions, and groups as objects which are intended
# to behave like the corresponding models but without any connection to SQL
# backend.
PermissionTuple = namedtuple(
    "PermissionTuple", ["id", "name", "description", "created_on", "audited"]
)
GroupTuple = namedtuple(
    "GroupTuple",
    ["id", "groupname", "name", "description", "canjoin", "enabled", "service_account", "type"],
)


# Raise these exceptions when asking about users or groups that are not cached.
class NoSuchUser(Exception):
    pass


class NoSuchGroup(Exception):
    pass


class GroupGraph(object):
    """The cached permission graph.

    Attributes:
        lock: Read lock on the data
        update_lock: Write lock on the data
        users: Names of all enabled users
        groups: Names of all enabled groups
        permissions: Names of all enabled permissions
        checkpoint: Revision of Grouper data
        checkpoint_time: Last update time of Grouper data
        user_metadata: Full information about each user
        group_metadata: Full information about each group
        group_service_accounts: Service accounts owned by groups
        permission_metadata: Permission grant information for users
        service_account_permissions: Permission grant information for service accounts
        permission_tuples: Metadata for all enabled permissions
        group_tuples: Metadata for all enabled groups
        disabled_group_tuples: Metadata for all disabled groups
    """

    def __init__(self):
        # type: () -> None
        self.logger = logging.getLogger(__name__)
        self._graph = None  # type: Optional[DiGraph]
        self._rgraph = None  # type: Optional[DiGraph]
        self.lock = RLock()
        self.update_lock = RLock()
        self.users = set()  # type: Set[str]
        self.groups = set()  # type: Set[str]
        self.permissions = set()  # type: Set[str]
        self.checkpoint = 0
        self.checkpoint_time = 0
        self.user_metadata = {}  # type: Dict[str, Dict[str, Any]]
        self.group_metadata = {}  # type: Dict[str, Dict[str, Any]]
        self.group_service_accounts = {}  # type: Dict[str, List[str]]
        self.permission_metadata = {}  # type: Dict[str, List[MappedPermission]]
        self.service_account_permissions = {}  # type: Dict[str, List[ServiceAccountPermission]]
        self.permission_tuples = set()  # type: Set[PermissionTuple]
        self.group_tuples = {}  # type: Dict[str, GroupTuple]
        self.disabled_group_tuples = {}  # type: Dict[str, GroupTuple]

    @property
    def nodes(self):
        with self.lock:
            return self._graph.nodes()

    @property
    def edges(self):
        with self.lock:
            return self._graph.edges()

    @classmethod
    def from_db(cls, session):
        inst = cls()
        inst.update_from_db(session)
        return inst

    def update_from_db(self, session):
        # Only allow one thread at a time to construct a fresh graph.
        with self.update_lock:
            checkpoint, checkpoint_time = self._get_checkpoint(session)
            if checkpoint == self.checkpoint:
                self.logger.debug("Checkpoint hasn't changed. Not Updating.")
                return
            self.logger.debug("Checkpoint changed; updating!")

            new_graph = DiGraph()
            new_graph.add_nodes_from(self._get_nodes_from_db(session))
            new_graph.add_edges_from(self._get_edges_from_db(session))
            rgraph = new_graph.reverse()

            users = set()
            groups = set()
            for (node_type, node_name) in new_graph.nodes():
                if node_type == "User":
                    users.add(node_name)
                elif node_type == "Group":
                    groups.add(node_name)

            user_metadata = self._get_user_metadata(session)
            permission_metadata = self._get_permission_metadata(session)
            service_account_permissions = all_service_account_permissions(session)
            group_metadata = self._get_group_metadata(session, permission_metadata)
            group_service_accounts = self._get_group_service_accounts(session)
            permission_tuples = self._get_permission_tuples(session)
            group_tuples = self._get_group_tuples(session)
            disabled_group_tuples = self._get_group_tuples(session, enabled=False)

            with self.lock:
                self._graph = new_graph
                self._rgraph = rgraph
                self.checkpoint = checkpoint
                self.checkpoint_time = checkpoint_time
                self.users = users
                self.groups = groups
                self.permissions = {
                    perm.permission
                    for perm_list in itervalues(permission_metadata)
                    for perm in perm_list
                }
                self.user_metadata = user_metadata
                self.group_metadata = group_metadata
                self.group_service_accounts = group_service_accounts
                self.permission_metadata = permission_metadata
                self.service_account_permissions = service_account_permissions
                self.permission_tuples = permission_tuples
                self.group_tuples = group_tuples
                self.disabled_group_tuples = disabled_group_tuples

    @staticmethod
    def _get_checkpoint(session):
        counter = session.query(Counter).filter_by(name="updates").scalar()
        if counter is None:
            return 0, 0
        return counter.count, int(counter.last_modified.strftime("%s"))

    @staticmethod
    def _get_user_metadata(session):
        """
        Returns a dict of username: { dict of metadata }.
        """

        def user_indexify(data):
            ret = defaultdict(list)
            for item in data:
                ret[item.user_id].append(item)
            return ret

        users = session.query(User)

        passwords = user_indexify(session.query(UserPassword).all())
        public_keys = user_indexify(session.query(PublicKey).all())
        user_metadata = user_indexify(session.query(UserMetadata).all())

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
                account = user.service_account
                out[user.username]["service_account"] = {
                    "description": account.description,
                    "machine_set": account.machine_set,
                }
                if account.owner:
                    out[user.username]["service_account"]["owner"] = account.owner.group.name
        return out

    # This describes how permissions are assigned to groups, NOT the intrinsic
    # metadata for a permission.
    @staticmethod
    def _get_permission_metadata(session):
        """
        Returns a dict of groupname: { list of permissions }. Note
        that disabled permissions are not included.
        """
        out = defaultdict(list)  # groupid -> [ ... ]

        permissions = session.query(Permission, PermissionMap).filter(
            Permission.id == PermissionMap.permission_id,
            PermissionMap.group_id == Group.id,
            Group.enabled == True,
            Permission.enabled == True,
        )

        for (permission, permission_map) in permissions:
            out[permission_map.group.name].append(
                MappedPermission(
                    permission=permission.name,
                    audited=permission.audited,
                    argument=permission_map.argument,
                    groupname=permission_map.group.name,
                    granted_on=permission_map.granted_on,
                    alias=False,
                )
            )

            aliases = get_plugin_proxy().get_aliases_for_mapped_permission(
                session, permission.name, permission_map.argument
            )

            for (name, arg) in aliases:
                out[permission_map.group.name].append(
                    MappedPermission(
                        permission=name,
                        audited=permission.audited,
                        argument=arg,
                        groupname=permission_map.group.name,
                        granted_on=permission_map.granted_on,
                        alias=True,
                    )
                )

        return out

    @staticmethod
    def _get_permission_tuples(session):
        """
        Returns a set of PermissionTuple instances.
        """
        # TODO: import here to avoid circular dependency
        from grouper.permissions import get_all_permissions

        out = set()
        permissions = get_all_permissions(session)
        for permission in permissions:
            out.add(
                PermissionTuple(
                    id=permission.id,
                    name=permission.name,
                    description=permission.description,
                    created_on=permission.created_on,
                    audited=permission._audited,
                )
            )
        return out

    @staticmethod
    def _get_group_metadata(session, permission_metadata):
        """
        Returns a dict of groupname: { dict of metadata }.
        """
        groups = session.query(Group).filter(Group.enabled == True)

        out = {}
        for group in groups:
            out[group.groupname] = {
                "permissions": [
                    {"permission": permission.permission, "argument": permission.argument}
                    for permission in permission_metadata[group.id]
                ],
                "contacts": {"email": group.email_address},
            }
        return out

    @staticmethod
    def _get_group_service_accounts(session):
        """
        Returns a dict of groupname: { list of service account names }.
        """
        out = defaultdict(list)
        tuples = session.query(Group, ServiceAccount).filter(
            GroupServiceAccount.group_id == Group.id,
            GroupServiceAccount.service_account_id == ServiceAccount.id,
        )
        for group, account in tuples:
            out[group.groupname].append(account.user.username)
        return out

    @staticmethod
    def _get_group_tuples(session, enabled=True):
        """
        Returns a dict of groupname: GroupTuple.
        """
        out = {}
        groups = (session.query(Group).order_by(Group.groupname)).filter(Group.enabled == enabled)
        for group in groups:
            out[group.groupname] = GroupTuple(
                id=group.id,
                groupname=group.groupname,
                name=group.groupname,
                description=group.description,
                canjoin=group.canjoin,
                enabled=group.enabled,
                service_account=is_role_user(session, group=group),
                type="Group",
            )
        return out

    @staticmethod
    def _get_nodes_from_db(session):
        return (
            session.query(label("type", literal("User")), label("name", User.username))
            .filter(User.enabled == True)
            .union(
                session.query(
                    label("type", literal("Group")), label("name", Group.groupname)
                ).filter(Group.enabled == True)
            )
            .all()
        )

    @staticmethod
    def _get_edges_from_db(session):

        parent = aliased(Group)
        group_member = aliased(Group)
        user_member = aliased(User)
        edges = []

        now = datetime.utcnow()

        query = (
            session.query(
                label("groupname", parent.groupname),
                label("type", literal("Group")),
                label("name", group_member.groupname),
                label("role", GroupEdge._role),
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

        for record in query.all():
            edges.append(
                (("Group", record.groupname), (record.type, record.name), {"role": record.role})
            )

        return edges

    def get_permissions(self, audited=False):
        # type: (bool) -> List[PermissionTuple]
        """Get the list of permissions as PermissionTuple instances."""
        with self.lock:
            if audited:
                permissions = [p for p in self.permission_tuples if p.audited]
            else:
                permissions = list(self.permission_tuples)
        return permissions

    def get_permission_details(self, name, expose_aliases=True):
        """ Get a permission and what groups and service accounts it's assigned to. """

        with self.lock:
            data = {"groups": {}, "service_accounts": {}}

            # Get all mapped versions of the permission. This is only direct relationships.
            direct_groups = set()
            for groupname, permissions in iteritems(self.permission_metadata):
                for permission in permissions:
                    if permission.permission == name:
                        data["groups"][groupname] = self.get_group_details(
                            groupname, show_permission=name, expose_aliases=expose_aliases
                        )
                        direct_groups.add(groupname)

            # Now find all members of these groups going down the tree.
            checked_groups = set()
            for groupname in direct_groups:
                group = ("Group", groupname)
                paths = single_source_shortest_path(self._graph, group, None)
                for member, path in iteritems(paths):
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
            for account, permissions in iteritems(self.service_account_permissions):
                for permission in permissions:
                    if permission.permission == name:
                        details = {
                            "permission": permission.permission,
                            "argument": permission.argument,
                            "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                        }
                        if account in data["service_accounts"]:
                            data["service_accounts"][account]["permissions"].append(details)
                        else:
                            data["service_accounts"][account] = {"permissions": [details]}

            return data

    def get_disabled_groups(self):
        """ Get the list of disabled groups as GroupTuple instances sorted by groupname. """
        with self.lock:
            return sorted(self.disabled_group_tuples.values(), key=lambda g: g.groupname)

    def get_groups(self, audited=False, directly_audited=False):
        """Get the list of groups as GroupTuple instances sorted by groupname.

        Arg(s):
            audited (bool): true to get only audited groups
            directly_audited (bool): true to get only directly audited
                groups (implies `audited` is true)

        Return:
            List of GroupTuple
        """
        if directly_audited:
            audited = True
        with self.lock:
            groups = sorted(self.group_tuples.values(), key=lambda g: g.groupname)
            if audited:

                def is_directly_audited(group):
                    for mp in self.permission_metadata[group.groupname]:
                        if mp.audited:
                            return True
                    return False

                directly_audited_groups = list(filter(is_directly_audited, groups))
                if directly_audited:
                    return directly_audited_groups
                queue = [("Group", group.groupname) for group in directly_audited_groups]
                audited_group_nodes = set()
                while len(queue):
                    g = queue.pop()
                    if g not in audited_group_nodes:
                        audited_group_nodes.add(g)
                        for nhbr in self._graph.neighbors(g):  # Members of g.
                            if nhbr[0] == "Group":
                                queue.append(nhbr)
                groups = sorted(
                    [self.group_tuples[group[1]] for group in audited_group_nodes],
                    key=lambda g: g.groupname,
                )
        return groups

    def get_group_details(self, groupname, cutoff=None, show_permission=None, expose_aliases=True):
        """ Get users and permissions that belong to a group. Raise NoSuchGroup
        for missing groups. """

        with self.lock:
            # This is calculated based on all the permissions that apply to this group. Since this
            # is a graph walk, we calculate it here when we're getting this data.
            group_audited = False
            data = {
                "users": {},
                "groups": {},
                "subgroups": {},
                "permissions": [],
                "audited": group_audited,
            }
            if groupname in self.group_service_accounts:
                data["service_accounts"] = self.group_service_accounts[groupname]

            group = ("Group", groupname)
            if not self._graph.has_node(group):
                raise NoSuchGroup("Group %s is either missing or disabled." % groupname)
            paths = single_source_shortest_path(self._graph, group, cutoff)
            rpaths = single_source_shortest_path(self._rgraph, group, cutoff)

            for member, path in iteritems(paths):
                if member == group:
                    continue
                member_type, member_name = member
                role = self._graph[group][path[1]]["role"]
                data[MEMBER_TYPE_MAP[member_type]][member_name] = {
                    "name": member_name,
                    "path": [elem[1] for elem in path],
                    "distance": len(path) - 1,
                    "role": role,
                    "rolename": GROUP_EDGE_ROLES[role],
                }

            for parent, path in iteritems(rpaths):
                if parent == group:
                    continue
                parent_type, parent_name = parent
                role = self._rgraph[path[-2]][parent]["role"]
                data["groups"][parent_name] = {
                    "name": parent_name,
                    "path": [elem[1] for elem in path],
                    "distance": len(path) - 1,
                    "role": role,
                    "rolename": GROUP_EDGE_ROLES[role],
                }
                for permission in self.permission_metadata.get(parent_name, []):
                    if show_permission is not None and permission.permission != show_permission:
                        continue
                    if permission.audited:
                        group_audited = True

                    perm_data = {
                        "permission": permission.permission,
                        "argument": permission.argument,
                        "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                        "distance": len(path) - 1,
                        "path": [elem[1] for elem in path],
                    }

                    if expose_aliases:
                        perm_data["alias"] = permission.alias

                    data["permissions"].append(perm_data)

            for permission in self.permission_metadata.get(groupname, []):
                if show_permission is not None and permission.permission != show_permission:
                    continue
                if permission.audited:
                    group_audited = True

                perm_data = {
                    "permission": permission.permission,
                    "argument": permission.argument,
                    "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                    "distance": 0,
                    "path": [groupname],
                }

                if expose_aliases:
                    perm_data["alias"] = permission.alias

                data["permissions"].append(perm_data)

            data["audited"] = group_audited
            return data

    def get_user_details(self, username, cutoff=None, expose_aliases=True):
        """ Get a user's groups and permissions.  Raise NoSuchUser for missing users."""
        max_dist = cutoff - 1 if (cutoff is not None) else None

        groups = {}
        permissions = []
        user_details = {"groups": groups, "permissions": permissions}

        with self.lock:
            if username not in self.user_metadata:
                raise NoSuchUser(username)

            user = ("User", username)

            # For disabled users or users introduced between SQL queries, just
            # return empty details.
            if not self._rgraph.has_node(user):
                return user_details

            # If the user is a service account, its permissions are only those of the service
            # account and we don't do any graph walking.
            if "service_account" in self.user_metadata[username]:
                if username in self.service_account_permissions:
                    for permission in self.service_account_permissions[username]:
                        permissions.append(
                            {
                                "permission": permission.permission,
                                "argument": permission.argument,
                                "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                            }
                        )
                return user_details

            # User permissions are inherited from all groups for which their
            # role is not "np-owner".  User groups are all groups in which a
            # user is a member by inheritance, except for ancestors of groups
            # where their role is "np-owner", unless the user is a member of
            # such an ancestor via a non-"np-owner" role in another group.
            rpaths = {}
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
                new_rpaths = single_source_shortest_path(self._rgraph, group, max_dist)
                for parent, path in iteritems(new_rpaths):
                    if parent not in rpaths or 1 + len(path) < len(rpaths[parent]):
                        rpaths[parent] = [user] + path

            for parent, path in iteritems(rpaths):
                if parent == user:
                    continue
                parent_type, parent_name = parent
                role = self._rgraph[path[-2]][parent]["role"]
                groups[parent_name] = {
                    "name": parent_name,
                    "path": [elem[1] for elem in path],
                    "distance": len(path) - 1,
                    "role": role,
                    "rolename": GROUP_EDGE_ROLES[role],
                }

                for permission in self.permission_metadata[parent_name]:
                    perm_data = {
                        "permission": permission.permission,
                        "argument": permission.argument,
                        "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                        "path": [elem[1] for elem in path],
                        "distance": len(path) - 1,
                    }

                    if expose_aliases:
                        perm_data["alias"] = permission.alias

                    permissions.append(perm_data)

            return user_details
