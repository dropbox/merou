from collections import defaultdict, namedtuple
from datetime import datetime
import logging
from threading import RLock

from networkx import DiGraph, single_source_shortest_path
from sqlalchemy import or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql import label, literal

from grouper.models.counter import Counter
from grouper.models.group import Group
from grouper.models.group_edge import GROUP_EDGE_ROLES, GroupEdge
from grouper.models.group_service_accounts import GroupServiceAccount
from grouper.models.permission import MappedPermission, Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.public_key import PublicKey
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User
from grouper.models.user_metadata import UserMetadata
from grouper.models.user_password import UserPassword
from grouper.public_key import get_all_public_key_tags
from grouper.role_user import is_role_user
from grouper.service_account import all_service_account_permissions
from grouper.util import singleton

MEMBER_TYPE_MAP = {
    "User": "users",
    "Group": "subgroups",
}
EPOCH = datetime(1970, 1, 1)


@singleton
def Graph():  # noqa
    return GroupGraph()

# A GroupGraph caches users, permissions, and groups as objects which are intended
# to behave like the corresponding models but without any connection to SQL
# backend.
PermissionTuple = namedtuple(
    "PermissionTuple",
    ["id", "name", "description", "created_on", "audited"])
GroupTuple = namedtuple(
    "GroupTuple",
    ["id", "groupname", "name", "description", "canjoin", "enabled", "service_account", "type"])


# Raise these exceptions when asking about users or groups that are not cached.
class NoSuchUser(Exception):
    pass


class NoSuchGroup(Exception):
    pass


class GroupGraph(object):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._graph = None
        self._rgraph = None
        self.lock = RLock()  # Graph structure.
        self.update_lock = RLock()  # Limit to 1 updating thread at a time.
        self.users = set()  # Enabled user names.
        self.groups = set()  # Group names.
        self.permissions = set()  # Permission names.
        self.checkpoint = 0
        self.checkpoint_time = 0
        self.user_metadata = {}  # username -> {metadata:[{}] public_keys:[{}]}.
        self.group_metadata = {}
        self.group_service_accounts = {}
        self.permission_metadata = {}  # TODO: rename.  This is about permission grants.
        self.service_account_permissions = {}
        self.permission_tuples = set()  # Mock Permission instances.
        self.group_tuples = {}  # groupname -> Mock Group instance.
        self.disabled_group_tuples = {}  # groupname -> Mock Group instance.

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
                self.permissions = {perm.permission
                                    for perm_list in permission_metadata.values()
                                    for perm in perm_list}
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
        '''
        Returns a dict of username: { dict of metadata }.
        '''

        def user_indexify(data):
            ret = defaultdict(list)
            for item in data:
                ret[item.user_id].append(item)
            return ret

        users = session.query(User)

        passwords = user_indexify(session.query(UserPassword).all())
        public_keys = user_indexify(session.query(PublicKey).all())
        user_metadata = user_indexify(session.query(UserMetadata).all())
        public_key_tags = get_all_public_key_tags(session)

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
                    } for password in passwords.get(user.id, [])
                ],
                "public_keys": [
                    {
                        "public_key": key.public_key,
                        "fingerprint": key.fingerprint,
                        "created_on": str(key.created_on),
                        "tags": [tag.name for tag in public_key_tags.get(key.id, [])],
                        "id": key.id,
                    } for key in public_keys.get(user.id, [])
                ],
                "metadata": [
                    {
                        "data_key": row.data_key,
                        "data_value": row.data_value,
                        "last_modified": str(row.last_modified),
                    } for row in user_metadata.get(user.id, [])
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
        '''
        Returns a dict of groupname: { list of permissions }.
        '''
        out = defaultdict(list)  # groupid -> [ ... ]
        permissions = session.query(Permission, PermissionMap).filter(
            Permission.id == PermissionMap.permission_id,
            PermissionMap.group_id == Group.id,
            Group.enabled == True,
        )
        for permission in permissions:
            out[permission[1].group.name].append(MappedPermission(
                permission=permission[0].name,
                audited=permission[0].audited,
                argument=permission[1].argument,
                groupname=permission[1].group.name,
                granted_on=permission[1].granted_on,
            ))
        return out

    @staticmethod
    def _get_permission_tuples(session):
        '''
        Returns a set of PermissionTuple instances.
        '''
        out = set()
        permissions = (
            session.query(Permission)
            .order_by(Permission.name)
        )
        for permission in permissions:
            out.add(PermissionTuple(
                id=permission.id,
                name=permission.name,
                description=permission.description,
                created_on=permission.created_on,
                audited=permission._audited,
            ))
        return out

    @staticmethod
    def _get_group_metadata(session, permission_metadata):
        '''
        Returns a dict of groupname: { dict of metadata }.
        '''
        groups = session.query(Group).filter(
            Group.enabled == True
        )

        out = {}
        for group in groups:
            out[group.groupname] = {
                "permissions": [
                    {
                        "permission": permission.permission,
                        "argument": permission.argument,
                    } for permission in permission_metadata[group.id]
                ],
                "contacts": {
                    "email": group.email_address,
                },

            }
        return out

    @staticmethod
    def _get_group_service_accounts(session):
        '''
        Returns a dict of groupname: { list of service account names }.
        '''
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
        '''
        Returns a dict of groupname: GroupTuple.
        '''
        out = {}
        groups = (
            session.query(Group)
            .order_by(Group.groupname)
        ).filter(
            Group.enabled == enabled
        )
        for group in groups:
            out[group.groupname] = GroupTuple(
                id=group.id,
                groupname=group.groupname,
                name=group.groupname,
                description=group.description,
                canjoin=group.canjoin,
                enabled=group.enabled,
                service_account=is_role_user(session, group=group),
                type="Group"
            )
        return out

    @staticmethod
    def _get_nodes_from_db(session):
        return session.query(
            label("type", literal("User")),
            label("name", User.username)
        ).filter(
            User.enabled == True
        ).union(session.query(
            label("type", literal("Group")),
            label("name", Group.groupname)
        ).filter(
            Group.enabled == True
        )).all()

    @staticmethod
    def _get_edges_from_db(session):

        parent = aliased(Group)
        group_member = aliased(Group)
        user_member = aliased(User)
        edges = []

        now = datetime.utcnow()

        query = session.query(
            label("groupname", parent.groupname),
            label("type", literal("Group")),
            label("name", group_member.groupname),
            label("role", GroupEdge._role)
        ).filter(
            parent.id == GroupEdge.group_id,
            group_member.id == GroupEdge.member_pk,
            GroupEdge.active == True,
            parent.enabled == True,
            group_member.enabled == True,
            or_(
                GroupEdge.expiration > now,
                GroupEdge.expiration == None
            ),
            GroupEdge.member_type == 1
        ).union(session.query(
            label("groupname", parent.groupname),
            label("type", literal("User")),
            label("name", user_member.username),
            label("role", GroupEdge._role)
        ).filter(
            parent.id == GroupEdge.group_id,
            user_member.id == GroupEdge.member_pk,
            GroupEdge.active == True,
            parent.enabled == True,
            user_member.enabled == True,
            or_(
                GroupEdge.expiration > now,
                GroupEdge.expiration == None
            ),
            GroupEdge.member_type == 0
        ))

        for record in query.all():
            edges.append((
                ("Group", record.groupname),
                (record.type, record.name),
                {"role": record.role},
            ))

        return edges

    def get_permissions(self, audited=False):
        """ Get the list of permissions as PermissionTuple instances sorted by name. """
        with self.lock:
            permissions = sorted(self.permission_tuples, key=lambda p: p.name)
        if audited:
            permissions = filter(lambda p: p.audited, permissions)
        return permissions

    def get_permission_details(self, name):
        """ Get a permission and what groups and service accounts it's assigned to. """

        with self.lock:
            data = {
                "groups": {},
                "service_accounts": {},
            }

            # Get all mapped versions of the permission. This is only direct relationships.
            direct_groups = set()
            for groupname, permissions in self.permission_metadata.iteritems():
                for permission in permissions:
                    if permission.permission == name:
                        data["groups"][groupname] = self.get_group_details(
                            groupname, show_permission=name)
                        direct_groups.add(groupname)

            # Now find all members of these groups going down the tree.
            checked_groups = set()
            for groupname in direct_groups:
                group = ("Group", groupname)
                paths = single_source_shortest_path(self._graph, group, None)
                for member, path in paths.iteritems():
                    if member == group:
                        continue
                    member_type, member_name = member
                    if member_type != 'Group':
                        continue
                    if member_name in checked_groups:
                        continue
                    checked_groups.add(member_name)
                    data["groups"][member_name] = self.get_group_details(
                        member_name, show_permission=name)

            # Finally, add all service accounts.
            for account, permissions in self.service_account_permissions.iteritems():
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
        """ Get the list of groups as GroupTuple instances sorted by groupname. """
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
                directly_audited_groups = filter(is_directly_audited, groups)
                if directly_audited:
                    return directly_audited_groups
                queue = [("Group", group.groupname) for group in directly_audited_groups]
                audited_group_nodes = set()
                while len(queue):
                    g = queue.pop()
                    if g not in audited_group_nodes:
                        audited_group_nodes.add(g)
                        for nhbr in self._graph.neighbors(g):  # Members of g.
                            if nhbr[0] == 'Group':
                                queue.append(nhbr)
                groups = sorted([self.group_tuples[group[1]] for group in audited_group_nodes],
                                key=lambda g: g.groupname)
        return groups

    def get_group_details(self, groupname, cutoff=None, show_permission=None):
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

            for member, path in paths.iteritems():
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

            for parent, path in rpaths.iteritems():
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
                    data["permissions"].append({
                        "permission": permission.permission,
                        "argument": permission.argument,
                        "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                        "distance": len(path) - 1,
                        "path": [elem[1] for elem in path],
                    })
            for permission in self.permission_metadata.get(groupname, []):
                if show_permission is not None and permission.permission != show_permission:
                    continue
                if permission.audited:
                    group_audited = True
                data["permissions"].append({
                    "permission": permission.permission,
                    "argument": permission.argument,
                    "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                    "distance": 0,
                    "path": [groupname],
                })

            data["audited"] = group_audited
            return data

    def get_user_details(self, username, cutoff=None):
        """ Get a user's groups and permissions.  Raise NoSuchUser for missing users."""
        max_dist = cutoff - 1 if (cutoff is not None) else None

        groups = {}
        permissions = []
        user_details = {
            "groups": groups,
            "permissions": permissions,
        }

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
                        permissions.append({
                            "permission": permission.permission,
                            "argument": permission.argument,
                            "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                        })
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
                for parent, path in new_rpaths.iteritems():
                    if parent not in rpaths or 1 + len(path) < len(rpaths[parent]):
                        rpaths[parent] = [user] + path

            for parent, path in rpaths.iteritems():
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
                    permissions.append({
                        "permission": permission.permission,
                        "argument": permission.argument,
                        "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                        "path": [elem[1] for elem in path],
                        "distance": len(path) - 1,
                    })

            return user_details
