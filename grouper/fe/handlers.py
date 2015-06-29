from datetime import datetime
import operator

from expvar.stats import stats
from tornado.web import RequestHandler

from sqlalchemy import union_all, or_, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import label, literal

import sshpubkey

from ..audit import assert_controllers_are_auditors, assert_can_join, UserNotAuditor
from ..constants import PERMISSION_GRANT, PERMISSION_CREATE, PERMISSION_AUDITOR

from .forms import (
    GroupCreateForm, GroupEditForm, GroupJoinForm, GroupAddForm, GroupRemoveForm,
    GroupRequestModifyForm, PublicKeyForm, PermissionCreateForm,
    PermissionGrantForm, GroupEditMemberForm,
)
from ..graph import NoSuchUser, NoSuchGroup
from ..models import (
    User, Group, Request, PublicKey, Permission, PermissionMap, AuditLog, GroupEdge, Counter,
    GROUP_JOIN_CHOICES, REQUEST_STATUS_CHOICES, GROUP_EDGE_ROLES, OBJ_TYPES,
    get_all_groups, get_all_users, get_user_or_group,
)
from .settings import settings
from .util import GrouperHandler, Alert, test_reserved_names
from ..util import matches_glob


class Index(GrouperHandler):
    def get(self):
        # For now, redirect to viewing your own profile. TODO: maybe have a
        # Grouper home page where you can maybe do stuff?
        return self.redirect("/users/{}".format(self.current_user.name))


class Search(GrouperHandler):
    def get(self):
        query = self.get_argument("query", "")
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        if limit > 9000:
            limit = 9000

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
    def get(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if user_id is not None:
            user = self.session.query(User).filter_by(id=user_id).scalar()
        else:
            user = self.session.query(User).filter_by(username=name).scalar()

        if not user:
            return self.notfound()

        can_control = False
        if (user.name == self.current_user.name) or self.current_user.user_admin:
            can_control = True

        try:
            user_md = self.graph.get_user_details(user.name)
        except NoSuchUser:
            # Either user is probably very new, so they have no metadata yet, or
            # they're disabled, so we've excluded them from the in-memory graph.
            user_md = {}

        groups = user.my_groups()
        public_keys = user.my_public_keys()
        permissions = user_md.get('permissions', [])
        log_entries = user.my_log_entries()
        self.render("user.html", user=user, groups=groups, public_keys=public_keys,
                    can_control=can_control, permissions=permissions,
                    log_entries=log_entries)


class PermissionsCreate(GrouperHandler):
    def get(self):
        can_create = self.current_user.my_creatable_permissions()
        if not can_create:
            return self.forbidden()

        return self.render(
            "permission-create.html", form=PermissionCreateForm(), can_create=can_create,
        )

    def post(self):
        can_create = self.current_user.my_creatable_permissions()
        if not can_create:
            return self.forbidden()

        form = PermissionCreateForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "permission-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        # A user is allowed to create a permission if the name matches any of the globs that they
        # are given access to via PERMISSION_CREATE, as long as the permission does not match a
        # reserved name. (Unless specifically granted.)
        allowed = False
        for creatable in can_create:
            if matches_glob(creatable, form.data["name"]):
                allowed = True

        for failure_message in test_reserved_names(form.data["name"]):
            form.name.errors.append(failure_message)

        if not allowed:
            form.name.errors.append(
                "Permission name does not match any of your allowed patterns."
            )

        if form.name.errors:
            return self.render(
                "permission-create.html", form=form,
                alerts=self.get_form_alerts(form.errors),
            )

        permission = Permission(name=form.data["name"], description=form.data["description"])
        try:
            permission.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append(
                "Name already in use. Permissions must be unique."
            )
            return self.render(
                "permission-create.html", form=form, can_create=can_create,
                alerts=self.get_form_alerts(form.errors),
            )

        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'create_permission',
                     'Created permission.', on_permission_id=permission.id)

        return self.redirect("/permissions/{}".format(permission.name))


class PermissionDisableAuditing(GrouperHandler):
    def post(self, user_id=None, name=None):
        if not self.current_user.permission_admin:
            return self.forbidden()

        permission = Permission.get(self.session, name)
        if not permission:
            return self.notfound()

        permission.disable_auditing()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'disable_auditing',
                     'Disabled auditing.', on_permission_id=permission.id)

        return self.redirect("/permissions/{}".format(permission.name))


class PermissionEnableAuditing(GrouperHandler):
    def post(self, name=None):
        if not self.current_user.permission_admin:
            return self.forbidden()

        permission = Permission.get(self.session, name)
        if not permission:
            return self.notfound()

        permission.enable_auditing()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'enable_auditing',
                     'Enabled auditing.', on_permission_id=permission.id)

        return self.redirect("/permissions/{}".format(permission.name))


class PermissionsGrant(GrouperHandler):
    def get(self, name=None):
        grantable = self.current_user.my_grantable_permissions()
        if not grantable:
            return self.forbidden()

        group = Group.get(self.session, None, name)
        if not group:
            return self.notfound()

        form = PermissionGrantForm()
        form.permission.choices = [["", "(select one)"]]
        for perm in grantable:
            grantable = "{} ({})".format(perm[0].name, perm[1])
            form.permission.choices.append([perm[0].name, grantable])

        return self.render(
            "permission-grant.html", form=form, group=group,
        )

    def post(self, name=None):
        grantable = self.current_user.my_grantable_permissions()
        if not grantable:
            return self.forbidden()

        group = Group.get(self.session, None, name)
        if not group:
            return self.notfound()

        form = PermissionGrantForm(self.request.arguments)
        form.permission.choices = [["", "(select one)"]]
        for perm in grantable:
            grantable_str = "{} ({})".format(perm[0].name, perm[1])
            form.permission.choices.append([perm[0].name, grantable_str])

        if not form.validate():
            return self.render(
                "permission-grant.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        permission = Permission.get(self.session, form.data["permission"])
        if not permission:
            return self.notfound()  # Shouldn't happen.

        allowed = False
        for perm in grantable:
            if perm[0].name == permission.name:
                if matches_glob(perm[1], form.data["argument"]):
                    allowed = True
        if not allowed:
            form.argument.errors.append(
                "You do not have grant authority over that permission/argument combination."
            )
            return self.render(
                "permission-grant.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        # If the permission is audited, then see if the subtree meets auditing requirements.
        if permission.audited:
            fail_message = ("Permission is audited and this group (or a subgroup) contains " +
                            "owners, np-owners, or managers who have not received audit training.")
            try:
                permission_ok = assert_controllers_are_auditors(group)
            except UserNotAuditor as e:
                permission_ok = False
                fail_message = e
            if not permission_ok:
                form.permission.errors.append(fail_message)
                return self.render(
                    "permission-grant.html", form=form, group=group,
                    alerts=self.get_form_alerts(form.errors),
                )

        try:
            group.grant_permission(permission, argument=form.data["argument"])
        except IntegrityError:
            form.argument.errors.append(
                "Permission and Argument already mapped to this group."
            )
            return self.render(
                "permission-grant.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'grant_permission',
                     'Granted permission with argument: {}'.format(form.data["argument"]),
                     on_permission_id=permission.id, on_group_id=group.id)

        return self.redirect("/groups/{}".format(group.name))


class PermissionsRevoke(GrouperHandler):
    def get(self, name=None, mapping_id=None):
        grantable = self.current_user.my_grantable_permissions()
        if not grantable:
            return self.forbidden()

        mapping = PermissionMap.get(self.session, id=mapping_id)
        if not mapping:
            return self.notfound()

        allowed = False
        for perm in grantable:
            if perm[0].name == mapping.permission.name:
                if matches_glob(perm[1], mapping.argument):
                    allowed = True
        if not allowed:
            return self.forbidden()

        self.render("permission-revoke.html", mapping=mapping)

    def post(self, name=None, mapping_id=None):
        grantable = self.current_user.my_grantable_permissions()
        if not grantable:
            return self.forbidden()

        mapping = PermissionMap.get(self.session, id=mapping_id)
        if not mapping:
            return self.notfound()

        allowed = False
        for perm in grantable:
            if perm[0].name == mapping.permission.name:
                if matches_glob(perm[1], mapping.argument):
                    allowed = True
        if not allowed:
            return self.forbidden()

        permission = mapping.permission
        group = mapping.group

        mapping.delete(self.session)
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'revoke_permission',
                     'Revoked permission with argument: {}'.format(mapping.argument),
                     on_group_id=group.id, on_permission_id=permission.id)

        return self.redirect('/groups/{}'.format(group.name))


class PermissionsView(GrouperHandler):
    '''
    Controller for viewing the major permissions list. There is no privacy here; the existence of
    a permission is public.
    '''
    def get(self):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        audited_only = bool(int(self.get_argument("audited", 0)))
        if limit > 9000:
            limit = 9000

        permissions = self.graph.get_permissions(audited=audited_only)
        total = len(permissions)
        permissions = permissions[offset:offset+limit]

        can_create = self.current_user.my_creatable_permissions()

        self.render(
            "permissions.html", permissions=permissions, offset=offset, limit=limit, total=total,
            can_create=can_create, audited_permissions=audited_only
        )


class PermissionView(GrouperHandler):
    def get(self, name=None):
        permission = Permission.get(self.session, name)
        if not permission:
            return self.notfound()

        can_delete = self.current_user.permission_admin
        mapped_groups = permission.get_mapped_groups()
        log_entries = permission.my_log_entries()

        self.render(
            "permission.html", permission=permission, can_delete=can_delete,
            mapped_groups=mapped_groups, log_entries=log_entries,
        )


class UsersView(GrouperHandler):
    def get(self):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        enabled = bool(int(self.get_argument("enabled", 1)))
        if limit > 9000:
            limit = 9000

        users = (
            self.session.query(User)
            .filter(User.enabled == enabled)
            .order_by(User.username)
        )
        total = users.count()
        users = users.offset(offset).limit(limit).all()

        self.render(
            "users.html", users=users, offset=offset, limit=limit, total=total,
            enabled=enabled,
        )


class UserEnable(GrouperHandler):
    def post(self, user_id=None, name=None):
        if not self.current_user.user_admin:
            return self.forbidden()

        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        user.enable()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'enable_user',
                     'Enabled user.', on_user_id=user.id)

        return self.redirect("/users/{}".format(user.name))


class UserDisable(GrouperHandler):
    def post(self, user_id=None, name=None):

        if not self.current_user.user_admin:
            return self.forbidden()

        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        user.disable(self.current_user)
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'disable_user',
                     'Disabled user.', on_user_id=user.id)

        return self.redirect("/users/{}".format(user.name))


class GroupView(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        grantable = self.current_user.my_grantable_permissions()

        try:
            group_md = self.graph.get_group_details(group.name)
        except NoSuchGroup:
            # Very new group with no metadata yet, or it has been disabled and
            # excluded from in-memory cache.
            group_md = {}

        members = group.my_members()
        groups = group.my_groups()
        permissions = group_md.get('permissions', [])
        audited = group_md.get('audited', False)
        log_entries = group.my_log_entries()
        num_pending = group.my_requests("pending").count()

        # Add mapping_id to permissions structure
        my_permissions = group.my_permissions()
        for perm_up in permissions:
            for perm_direct in my_permissions:
                if (perm_up['permission'] == perm_direct.name
                        and perm_up['argument'] == perm_direct.argument):
                    perm_up['mapping_id'] = perm_direct.mapping_id
                    break

        alerts = []
        self_pending = group.my_requests("pending", user=self.current_user).count()
        if self_pending:
            alerts.append(Alert('info', 'You have a pending request to join this group.', None))

        self.render(
            "group.html", group=group, members=members, groups=groups,
            num_pending=num_pending, alerts=alerts, permissions=permissions,
            log_entries=log_entries, grantable=grantable, audited=audited,
        )


class GroupEditMember(GrouperHandler):
    def get(self, group_id=None, name=None, name2=None, member_type=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if self.current_user.name == name2:
            return self.forbidden()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        member = members.get((member_type.capitalize(), name2), None)
        if not member:
            return self.notfound()

        edge = GroupEdge.get(
            self.session,
            group_id=group.id,
            member_type=OBJ_TYPES[member.type],
            member_pk=member.id,
        )
        if not edge:
            return self.notfound()

        form = GroupEditMemberForm(self.request.arguments)
        form.role.choices = [["member", "Member"]]
        if my_role in ("owner", "np-owner"):
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["owner", "Owner"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])

        form.role.data = edge.role
        form.expiration.data = edge.expiration.strftime("%m/%d/%Y") if edge.expiration else None

        self.render(
            "group-edit-member.html", group=group, member=member, edge=edge, form=form,
        )

    def post(self, group_id=None, name=None, name2=None, member_type=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if self.current_user.name == name2:
            return self.forbidden()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        member = members.get((member_type.capitalize(), name2), None)
        if not member:
            return self.notfound()

        if member.type == "Group":
            user_or_group = Group.get(self.session, member.id)
        else:
            user_or_group = User.get(self.session, member.id)
        if not user_or_group:
            return self.notfound()

        edge = GroupEdge.get(
            self.session,
            group_id=group.id,
            member_type=OBJ_TYPES[member.type],
            member_pk=member.id,
        )
        if not edge:
            return self.notfound()

        form = GroupEditMemberForm(self.request.arguments)
        form.role.choices = [["member", "Member"]]
        if my_role in ("owner", "np-owner"):
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["owner", "Owner"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])

        if not form.validate():
            return self.render(
                "group-edit-member.html", group=group, member=member, edge=edge, form=form,
                alerts=self.get_form_alerts(form.errors),
            )

        fail_message = 'This join is denied with this role at this time.'
        try:
            user_can_join = assert_can_join(group, user_or_group, role=form.data["role"])
        except UserNotAuditor as e:
            user_can_join = False
            fail_message = e
        if not user_can_join:
            return self.render(
                "group-edit-member.html", form=form, group=group, member=member, edge=edge,
                alerts=[
                    Alert('danger', fail_message, 'Audit Policy Enforcement')
                ]
            )

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")

        group.edit_member(self.current_user, user_or_group, form.data["reason"],
                          role=form.data["role"], expiration=expiration)

        return self.redirect("/groups/{}".format(group.name))


class GroupRequestUpdate(GrouperHandler):
    def get(self, request_id, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        if my_role not in ("manager", "owner", "np-owner"):
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

    def post(self, request_id, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        if my_role not in ("manager", "owner", "np-owner"):
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

        # We have to test this here, too, to ensure that someone can't sneak in with a pending
        # request that used to be allowed.
        if form.data["status"] != "cancelled":
            fail_message = 'This join is denied with this role at this time.'
            try:
                user_can_join = assert_can_join(request.requesting, request.get_on_behalf(),
                                                role=request.edge.role)
            except UserNotAuditor as e:
                user_can_join = False
                fail_message = e
            if not user_can_join:
                return self.render(
                    "group-request-update.html", group=group, request=request,
                    members=members, form=form, statuses=REQUEST_STATUS_CHOICES, updates=updates,
                    alerts=[
                        Alert('danger', fail_message, 'Audit Policy Enforcement')
                    ]
                )

        request.update_status(
            self.current_user,
            form.data["status"],
            form.data["reason"]
        )
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'update_request',
                     'Updated request to status: {}'.format(form.data["status"]),
                     on_group_id=group.id, on_user_id=request.requester.id)

        return self.redirect("/groups/{}/requests".format(group.name))

    def _get_choices(self, current_status):
        return [["", ""]] + [
            [status] * 2
            for status in REQUEST_STATUS_CHOICES[current_status]
        ]


class GroupRequests(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        status = self.get_argument("status", None)
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        if limit > 9000:
            limit = 9000

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
        limit = int(self.get_argument("limit", 100))
        enabled = bool(int(self.get_argument("enabled", 1)))
        audited_only = bool(int(self.get_argument("audited", 0)))
        if limit > 9000:
            limit = 9000

        if not enabled:
            groups = self.graph.get_disabled_groups()
            directly_audited_groups = None
        elif audited_only:
            groups = self.graph.get_groups(audited=True, directly_audited=False)
            directly_audited_groups = set([g.groupname for g in self.graph.get_groups(
                audited=True, directly_audited=True)])
        else:
            groups = self.graph.get_groups(audited=False)
            directly_audited_groups = set()
        total = len(groups)
        groups = groups[offset:offset+limit]

        form = GroupCreateForm()

        self.render(
            "groups.html", groups=groups, form=form,
            offset=offset, limit=limit, total=total, audited_groups=audited_only,
            directly_audited_groups=directly_audited_groups, enabled=enabled,
        )

    def post(self):
        form = GroupCreateForm(self.request.arguments)
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

        group.add_member(user, user, "Group Creator", "actioned", None, form.data["creatorrole"])
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'create_group',
                     'Created new group.', on_group_id=group.id)

        return self.redirect("/groups/{}".format(group.name))


class GroupAdd(GrouperHandler):
    def get_form(self, role=None):
        """Helper to create a GroupAddForm populated with all users and groups as options.

        Note that the first choice is blank so the first user alphabetically
        isn't always selected.

        Returns:
            GroupAddForm object.
        """

        form = GroupAddForm(self.request.arguments)

        form.role.choices = [["member", "Member"]]
        if role in ("owner", "np-owner"):
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["owner", "Owner"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])

        group_choices = [
            (group.groupname, "Group: " + group.groupname)  # (value, label)
            for group in get_all_groups(self.session)
        ]
        user_choices = [
            (user.username, "User: " + user.username)  # (value, label)
            for user in get_all_users(self.session)
        ]

        form.member.choices = [("", "")] + sorted(
            group_choices + user_choices,
            key=operator.itemgetter(1)
        )
        return form

    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        return self.render(
            "group-add.html", form=self.get_form(role=my_role), group=group
        )

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        form = self.get_form(role=my_role)
        if not form.validate():
            return self.render(
                "group-add.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        member = get_user_or_group(self.session, form.data["member"])
        if not member:
            form.member.errors.append("User or group not found.")
        elif (member.type, member.name) in group.my_members():
            form.member.errors.append("User or group is already a member of this group.")
        elif group.name == member.name:
            form.member.errors.append("By definition, this group is a member of itself already.")

        if form.member.errors:
            return self.render(
                "group-add.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")

        group.add_member(
            requester=self.current_user,
            user_or_group=member,
            reason=form.data["reason"],
            status='actioned',
            expiration=expiration,
            role=form.data["role"]
        )
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'join_group',
                     '{} added to group with role: {}'.format(
                         member.name, form.data["role"]),
                     on_group_id=group.id)

        return self.redirect("/groups/{}".format(group.name))


class GroupRemove(GrouperHandler):
    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        form = GroupRemoveForm(self.request.arguments)
        if not form.validate():
            return self.send_error(status_code=400)

        member_type, member_name = form.data["member_type"], form.data["member"]

        members = group.my_members()
        if not members.get((member_type.capitalize(), member_name), None):
            return self.notfound()

        removed_member = get_user_or_group(self.session, member_name, user_or_group=member_type)

        if self.current_user == removed_member:
            return self.send_error(
                status_code=400,
                reason="Can't remove yourself. Leave group instead."
            )

        group.revoke_member(self.current_user, removed_member, "Removed by owner/np-owner/manager")
        AuditLog.log(self.session, self.current_user.id, 'remove_from_group',
                     '{} was removed from the group.'.format(removed_member.name),
                     on_group_id=group.id, on_user_id=removed_member.id)
        return self.redirect("/groups/{}".format(group.name))


class GroupJoin(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        group_md = self.graph.get_group_details(group.name)

        form = GroupJoinForm()
        form.member.choices = self._get_choices(group)
        return self.render(
            "group-join.html", form=form, group=group, audited=group_md["audited"],
        )

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
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

        fail_message = 'This join is denied with this role at this time.'
        try:
            user_can_join = assert_can_join(group, member, role=form.data["role"])
        except UserNotAuditor as e:
            user_can_join = False
            fail_message = e
        if not user_can_join:
            return self.render(
                "group-join.html", form=form, group=group,
                alerts=[
                    Alert('danger', fail_message, 'Audit Policy Enforcement')
                ]
            )

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

        if group.canjoin == 'canask':
            AuditLog.log(self.session, self.current_user.id, 'join_group',
                         '{} requested to join with role: {}'.format(
                             member.name, form.data["role"]),
                         on_group_id=group.id)

            mail_to = [
                user.name
                for user in group.my_users()
                if GROUP_EDGE_ROLES[user.role] in ('manager', 'owner', 'np-owner')
            ]

            self.send_email(mail_to, 'Request to join: {}'.format(group.name), 'pending_request', {
                "requester": member.name,
                "requested_by": self.current_user.name,
                "requested": group.name,
                "reason": form.data["reason"],
                "expiration": expiration,
                "role": form.data["role"],
            })

        elif group.canjoin == 'canjoin':
            AuditLog.log(self.session, self.current_user.id, 'join_group',
                         '{} auto-approved to join with role: {}'.format(
                             member.name, form.data["role"]),
                         on_group_id=group.id)
        else:
            raise Exception('Need to update the GroupJoin.post audit logging')

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
            if _group.role < 1:  # manager, owner, and np-owner only.
                continue
            if ("Group", _group.name) in members:
                continue

            choices.append(
                ("Group: {}".format(_group.name), ) * 2
            )

        return choices


class GroupLeave(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not self.current_user.my_role(members):
            return self.forbidden()

        return self.render(
            "group-leave.html", group=group
        )

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not self.current_user.my_role(members):
            return self.forbidden()

        group.revoke_member(self.current_user, self.current_user, "User self-revoked.")

        AuditLog.log(self.session, self.current_user.id, 'leave_group',
                     '{} left the group.'.format(self.current_user.name),
                     on_group_id=group.id)

        return self.redirect("/groups/{}".format(group.name))


class GroupEdit(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        form = GroupEditForm(obj=group)

        self.render("group-edit.html", group=group, form=form)

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        form = GroupEditForm(self.request.arguments, obj=group)
        if not form.validate():
            return self.render(
                "group-edit.html", group=group, form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        group.groupname = form.data["groupname"]
        group.description = form.data["description"]
        group.canjoin = form.data["canjoin"]
        Counter.incr(self.session, "updates")

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

        AuditLog.log(self.session, self.current_user.id, 'edit_group',
                     'Edited group.', on_group_id=group.id)

        return self.redirect("/groups/{}".format(group.name))


class GroupEnable(GrouperHandler):
    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not self.current_user.my_role(members) in ("owner", "np-owner"):
            return self.forbidden()

        group.enable()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'enable_group',
                     'Enabled group.', on_group_id=group.id)

        return self.redirect("/groups/{}".format(group.name))


class GroupDisable(GrouperHandler):
    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not self.current_user.my_role(members) in ("owner", "np-owner"):
            return self.forbidden()

        group.disable()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'disable_group',
                     'Disabled group.', on_group_id=group.id)

        return self.redirect("/groups/{}".format(group.name))


class PublicKeyAdd(GrouperHandler):
    def get(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        self.render("public-key-add.html", form=PublicKeyForm(), user=user)

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
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

        AuditLog.log(self.session, self.current_user.id, 'add_public_key',
                     'Added public key: {}'.format(pubkey.fingerprint),
                     on_user_id=user.id)

        return self.redirect("/users/{}".format(user.name))


class PublicKeyDelete(GrouperHandler):
    def get(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        key = self.session.query(PublicKey).filter_by(id=key_id, user_id=user.id).scalar()
        if not key:
            return self.notfound()

        self.render("public-key-delete.html", user=user, key=key)

    def post(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        key = self.session.query(PublicKey).filter_by(id=key_id, user_id=user.id).scalar()
        if not key:
            return self.notfound()

        key.delete(self.session)
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'delete_public_key',
                     'Deleted public key: {}'.format(key.fingerprint),
                     on_user_id=user.id)

        return self.redirect("/users/{}".format(user.name))


class Help(GrouperHandler):
    def get(self):
        permissions = (
            self.session.query(Permission)
            .order_by(Permission.name)
        )
        d = {permission.name: permission for permission in permissions}

        self.render("help.html",
                    how_to_get_help=settings.how_to_get_help,
                    site_docs=settings.site_docs,
                    grant_perm=d[PERMISSION_GRANT],
                    create_perm=d[PERMISSION_CREATE],
                    audit_perm=d[PERMISSION_AUDITOR])


# Don't use GraphHandler here as we don't want to count
# these as requests.
class Stats(RequestHandler):
    def get(self):
        return self.write(stats.to_dict())


class NotFound(GrouperHandler):
    def get(self):
        return self.notfound()
