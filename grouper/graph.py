from collections import defaultdict
from datetime import datetime
from networkx import DiGraph, single_source_shortest_path
from threading import RLock
import logging

from sqlalchemy import or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql import label, literal

from .models import (
    Group, User, GroupEdge, PublicKey, UserMetadata, Counter, GROUP_EDGE_ROLES,
    Permission, PermissionMap, MappedPermission,
)
from .util import singleton


MEMBER_TYPE_MAP = {
    "User": "users",
    "Group": "subgroups",
}
EPOCH = datetime(1970, 1, 1)


@singleton
def Graph():  # noqa
    return GroupGraph()


class GroupGraph(object):
    def __init__(self):
        logging.info('Created graph object.')
        self._graph = None
        self._rgraph = None
        self.lock = RLock()
        self.users = set()
        self.groups = set()
        self.permissions = set()
        self.checkpoint = 0
        self.checkpoint_time = 0
        self.user_metadata = {}
        self.group_metadata = {}
        self.permission_metadata = {}

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

        checkpoint, checkpoint_time = self._get_checkpoint(session)
        if checkpoint == self.checkpoint:
            logging.debug("Checkpoint hasn't changed. Not Updating.")
            return
        logging.debug("Checkpoint changed; updating!")

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
        group_metadata = self._get_group_metadata(session, permission_metadata)

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
            self.permission_metadata = permission_metadata

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
        users = session.query(User).filter(
            User.enabled == True
        )

        public_keys = {}
        for key in session.query(PublicKey):
            if key.user_id not in public_keys:
                public_keys[key.user_id] = []
            public_keys[key.user_id].append(key)

        user_metadata = {}
        for row in session.query(UserMetadata):
            if row.user_id not in user_metadata:
                user_metadata[row.user_id] = []
            user_metadata[row.user_id].append(row)

        out = {}
        for user in users:
            out[user.username] = {
                "public_keys": [
                    {
                        "public_key": key.public_key,
                        "fingerprint": key.fingerprint,
                        "created_on": str(key.created_on),
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
        return out

    @staticmethod
    def _get_permission_metadata(session):
        '''
        Returns a dict of groupname: { list of permissions }.
        '''
        out = defaultdict(list)  # groupid -> [ ... ]
        permissions = session.query(Permission, PermissionMap).filter(
            Permission.id == PermissionMap.permission_id
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
                        "audited": permission.audited,
                    } for permission in permission_metadata[group.id]
                ],
            }
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
            label("name", Group.groupname))
        ).filter(
            Group.enabled == True
        ).all()

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

    def get_permission_details(self, name):
        """ Get a permission and what groups it's assigned to. """

        with self.lock:
            data = {
                "groups": {},
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

            return data

    def get_group_details(self, groupname, cutoff=None, show_permission=None):
        """ Get users and permissions that belong to a group. """

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

            group = ("Group", groupname)
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
                        "audited": permission.audited,
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
                    "audited": permission.audited,
                    "argument": permission.argument,
                    "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                    "distance": 0,
                    "path": [groupname],
                })

            data["audited"] = group_audited
            return data

    def get_user_details(self, username, cutoff=None):
        """ Get groups that a user belongs to."""

        with self.lock:
            groups = {}

            user = ("User", username)
            rpaths = single_source_shortest_path(self._rgraph, user, cutoff)

            permissions = []

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
                        "audited": permission.audited,
                        "argument": permission.argument,
                        "granted_on": (permission.granted_on - EPOCH).total_seconds(),
                        "path": [elem[1] for elem in path],
                        "distance": len(path) - 1,
                    })

            return {
                "groups": groups,
                "permissions": permissions,
            }
