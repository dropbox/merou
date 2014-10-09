from datetime import datetime
from networkx import DiGraph, single_source_shortest_path
from threading import RLock
import logging

from sqlalchemy import or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql import label, literal

from .models import Group, User, GroupEdge, Counter, GROUP_EDGE_ROLES


MEMBER_TYPE_MAP = {
    "User": "users",
    "Group": "subgroups",
}


class GroupGraph(object):
    def __init__(self):
        self._graph = None
        self._rgraph = None
        self.lock = RLock()
        self.users = set()
        self.groups = set()
        self.checkpoint = 0
        self.checkpoint_time = 0

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

        with self.lock:
            self._graph = new_graph
            self._rgraph = rgraph
            self.checkpoint = checkpoint
            self.checkpoint_time = checkpoint_time
            self.users = users
            self.groups = groups
            self.user_metadata = user_metadata

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

        out = {}
        for user in users:
            out[user.username] = {
                "public_keys": [
                    {
                        "public_key": key.public_key,
                        "fingerprint": key.fingerprint,
                        "created_on": str(key.created_on),
                    } for key in user.my_public_keys()
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
            label("membername", group_member.groupname),
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
            label("membername", user_member.username),
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
                (record.type, record.membername),
                {"role": record.role},
            ))

        return edges

    def get_group_details(self, groupname, cutoff=None):
        """ Get users that belong to a group."""

        with self.lock:

            data = {
                "users": {},
                "groups": {},
                "subgroups": {},
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

            return data

    def get_user_details(self, username, cutoff=None):
        """ Get groups that a user belongs to."""

        with self.lock:

            groups = {}

            user = ("User", username)
            rpaths = single_source_shortest_path(self._rgraph, user, cutoff)

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

            return {"groups": groups}
