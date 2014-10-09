from datetime import datetime
from expvar.stats import stats
from tornado.web import RequestHandler

from sqlalchemy import union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import label, literal

import sshpubkey

from .util import GrouperHandler, Alert
from .forms import GroupForm, GroupJoinForm, GroupRequestModifyForm, PublicKeyForm
from ..models import (
    User, Group, Request, PublicKey, GROUP_JOIN_CHOICES,
    REQUEST_STATUS_CHOICES,
)


class Index(GrouperHandler):
    def get(self):
        user = self.get_current_user()
        groups = user.my_groups()
        self.render("index.html", user=user, groups=groups)


class Search(GrouperHandler):
    def get(self):
        query = self.get_argument("query", "")
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 10))
        if limit > 50:
            limit = 50

        groups = self.session.query(
            label("type", literal("Group")),
            label("id", Group.id),
            label("name", Group.groupname)
        ).filter(
            Group.enabled == True,
            Group.groupname.like("%{}%".format(query))
        ).subquery()

        users = self.session.query(
            label("type", literal("User")),
            label("id", User.id),
            label("name", User.username)
        ).filter(
            User.enabled == True,
            User.username.like("%{}%".format(query))
        ).subquery()

        results_query = self.session.query(
            "type", "id", "name"
        ).select_entity_from(
            union_all(users.select(), groups.select())
        )
        total = results_query.count()
        results = results_query.offset(offset).limit(limit).all()

        if len(results) == 1:
            result = results[0]
            return self.redirect("/{}s/{}".format(result.type.lower(), result.name))

        self.render("search.html", results=results, search_query=query,
                    offset=offset, limit=limit, total=total)


class UserView(GrouperHandler):
    def get(self, user_id=None, username=None):
        user = User.get(self.session, user_id, username)
        if user_id is not None:
            user = self.session.query(User).filter_by(id=user_id).scalar()
        else:
            user = self.session.query(User).filter_by(username=username).scalar()

        if not user:
            return self.notfound()

        can_control = False
        if (user.name == self.current_user.name) or self.current_user.user_admin:
            can_control = True

        groups = user.my_groups()
        public_keys = user.my_public_keys()
        self.render("user.html", user=user, groups=groups, public_keys=public_keys,
                    can_control=can_control)


class UsersView(GrouperHandler):
    def get(self):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 10))
        if limit > 50:
            limit = 50

        users = (
            self.session.query(User)
            .filter(User.enabled == True)
            .order_by(User.username)
        )
        total = users.count()
        users = users.offset(offset).limit(limit).all()

        self.render(
            "users.html", users=users, offset=offset, limit=limit, total=total
        )


class UserEnable(GrouperHandler):
    def post(self, user_id=None, username=None):
        if not self.current_user.user_admin:
            return self.forbidden()

        user = User.get(self.session, user_id, username)
        if not user:
            return self.notfound()

        user.enable()
        self.session.commit()

        return self.redirect("/users/{}".format(user.name))


class UserDisable(GrouperHandler):
    def post(self, user_id=None, username=None):

        if not self.current_user.user_admin:
            return self.forbidden()

        user = User.get(self.session, user_id, username)
        if not user:
            return self.notfound()

        user.disable(self.current_user)
        self.session.commit()

        return self.redirect("/users/{}".format(user.name))


class GroupView(GrouperHandler):
    def get(self, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        members = group.my_members()
        groups = group.my_groups()

        num_pending = group.my_requests("pending").count()

        alerts = []
        self_pending = group.my_requests("pending", user=self.current_user).count()
        if self_pending:
            alerts.append(Alert('info', 'You have a pending request to join this group.', None))

        self.render(
            "group.html", group=group, members=members, groups=groups,
            num_pending=num_pending, alerts=alerts
        )


class GroupRequestUpdate(GrouperHandler):
    def get(self, request_id, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        if my_role not in ("manager", "owner"):
            return self.forbidden()

        request = self.session.query(Request).filter_by(id=request_id).scalar()
        if not request:
            return self.notfound()

        form = GroupRequestModifyForm()
        form.status.choices = self._get_choices(request.status)

        updates = request.my_status_updates()

        self.render(
            "group-request-update.html", group=group, request=request,
            members=members, form=form, statuses=REQUEST_STATUS_CHOICES, updates=updates
        )

    def post(self, request_id, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        if my_role not in ("manager", "owner"):
            return self.forbidden()

        request = self.session.query(Request).filter_by(id=request_id).scalar()
        if not request:
            return self.notfound()

        form = GroupRequestModifyForm(self.request.arguments)
        form.status.choices = self._get_choices(request.status)

        updates = request.my_status_updates()

        if not form.validate():
            return self.render(
                "group-request-update.html", group=group, request=request,
                members=members, form=form, alerts=self.get_form_alerts(form.errors),
                statuses=REQUEST_STATUS_CHOICES, updates=updates
            )

        request.update_status(
            self.current_user,
            form.data["status"],
            form.data["reason"]
        )
        self.session.commit()

        return self.redirect("/groups/{}/requests".format(group.name))

    def _get_choices(self, current_status):
        return [["", ""]] + [
            [status] * 2
            for status in REQUEST_STATUS_CHOICES[current_status]
        ]


class GroupRequests(GrouperHandler):
    def get(self, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        status = self.get_argument("status", None)
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 10))
        if limit > 50:
            limit = 50

        requests = group.my_requests(status).order_by(
            Request.requested_at.desc()
        )
        members = group.my_members()

        total = requests.count()
        requests = requests.offset(offset).limit(limit)

        self.render(
            "group-requests.html", group=group, requests=requests,
            members=members, status=status, statuses=REQUEST_STATUS_CHOICES,
            offset=offset, limit=limit, total=total
        )


class GroupsView(GrouperHandler):
    def get(self):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 10))
        if limit > 50:
            limit = 50

        groups = (
            self.session.query(Group)
            .filter(Group.enabled == True)
            .order_by(Group.groupname)
        )

        total = groups.count()
        groups = groups.offset(offset).limit(limit).all()
        form = GroupForm()

        self.render(
            "groups.html", groups=groups, form=form,
            offset=offset, limit=limit, total=total
        )

    def post(self):
        form = GroupForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "group-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        user = self.get_current_user()

        group = Group(
            groupname=form.data["groupname"],
            description=form.data["description"],
            canjoin=form.data["canjoin"]
        )
        try:
            group.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.groupname.errors.append(
                "{} already exists".format(form.data["groupname"])
            )
            return self.render(
                "group-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        group.add_member(user, user, "Group Creator", "actioned", None, "owner")
        self.session.commit()

        return self.redirect("/groups/{}".format(group.name))


class GroupJoin(GrouperHandler):
    def get(self, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        form = GroupJoinForm()
        form.member.choices = self._get_choices(group)
        return self.render(
            "group-join.html", form=form, group=group
        )

    def post(self, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        form = GroupJoinForm(self.request.arguments)
        form.member.choices = self._get_choices(group)
        if not form.validate():
            return self.render(
                "group-join.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        member = self._get_member(form.data["member"])

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")

        group.add_member(
            requester=self.current_user,
            user_or_group=member,
            reason=form.data["reason"],
            status=GROUP_JOIN_CHOICES[group.canjoin],
            expiration=expiration,
            role=form.data["role"]
        )
        self.session.commit()

        return self.redirect("/groups/{}".format(group.name))

    def _get_member(self, member_choice):
        member_type, member_name = member_choice.split(": ", 1)
        resource = None

        if member_type == "User":
            resource = User
        elif member_type == "Group":
            resource = Group

        if resource is None:
            return

        return self.session.query(resource).filter_by(
            name=member_name, enabled=True
        ).one()

    def _get_choices(self, group):
        choices = []

        members = group.my_members()

        if ("User", self.current_user.name) not in members:
            choices.append(
                ("User: {}".format(self.current_user.name), ) * 2
            )

        for _group in self.current_user.my_groups():
            if group.name == _group.name:  # Don't add self.
                continue
            if _group.role < 1:  # manager and owner only.
                continue
            if ("Group", _group.name) in members:
                continue

            choices.append(
                ("Group: {}".format(_group.name), ) * 2
            )

        return choices


class GroupEdit(GrouperHandler):
    def get(self, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        if my_role not in ("manager", "owner"):
            return self.forbidden()

        form = GroupForm(obj=group)

        self.render("group-edit.html", group=group, form=form)

    def post(self, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        if my_role not in ("manager", "owner"):
            return self.forbidden()

        form = GroupForm(self.request.arguments, obj=group)
        if not form.validate():
            return self.render(
                "group-edit.html", group=group, form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        group.groupname = form.data["groupname"]
        group.description = form.data["description"]
        group.canjoin = form.data["canjoin"]

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            form.groupname.errors.append(
                "{} already exists".format(form.data["groupname"])
            )
            return self.render(
                "group-edit.html", group=group, form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        return self.redirect("/groups/{}".format(group.name))


class GroupEnable(GrouperHandler):
    def post(self, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        members = group.my_members()
        if self.current_user.my_role(members) != "owner":
            return self.forbidden()

        group.enable()
        self.session.commit()

        return self.redirect("/groups/{}".format(group.name))


class GroupDisable(GrouperHandler):
    def post(self, group_id=None, groupname=None):
        group = Group.get(self.session, group_id, groupname)
        if not group:
            return self.notfound()

        members = group.my_members()
        if self.current_user.my_role(members) != "owner":
            return self.forbidden()

        group.disable()
        self.session.commit()

        return self.redirect("/groups/{}".format(group.name))


class PublicKeyAdd(GrouperHandler):
    def get(self, user_id=None, username=None):
        user = User.get(self.session, user_id, username)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        self.render("public-key-add.html", form=PublicKeyForm(), user=user)

    def post(self, user_id=None, username=None):
        user = User.get(self.session, user_id, username)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        form = PublicKeyForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "public-key-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        pubkey = sshpubkey.PublicKey.from_str(form.data["public_key"])
        db_pubkey = PublicKey(
            user=user,
            public_key='%s %s %s' % (pubkey.key_type, pubkey.key, pubkey.comment),
            fingerprint=pubkey.fingerprint,
        )
        try:
            db_pubkey.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.public_key.errors.append(
                "Key already in use. Public keys must be unique."
            )
            return self.render(
                "public-key-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        self.session.commit()

        return self.redirect("/users/{}".format(user.name))


class PublicKeyDelete(GrouperHandler):
    def get(self, user_id=None, username=None, key_id=None):
        user = User.get(self.session, user_id, username)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        try:
            key = user.my_public_keys(key_id=key_id)[0]
        except IndexError:
            return self.notfound()

        self.render("public-key-delete.html", user=user, key=key)

    def post(self, user_id=None, username=None, key_id=None):
        user = User.get(self.session, user_id, username)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        key = self.session.query(PublicKey).filter_by(id=key_id, user_id=user.id).scalar()
        if not key:
            return self.notfound()

        key.delete(self.session)
        self.session.commit()

        return self.redirect("/users/{}".format(user.name))


class Help(GrouperHandler):
    def get(self):
        self.render("help.html")


# Don't use GraphHandler here as we don't want to count
# these as requests.
class Stats(RequestHandler):
    def get(self):
        return self.write(stats.to_dict())


class NotFound(GrouperHandler):
    def get(self):
        return self.notfound()
