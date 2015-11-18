from datetime import datetime, timedelta
import operator

from expvar.stats import stats
from tornado.web import RequestHandler
from sqlalchemy import union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import label, literal

from .. import perf_profile
from .. import public_key
from ..audit import assert_controllers_are_auditors, assert_can_join, get_audits, UserNotAuditor
from ..constants import (
    PERMISSION_GRANT, PERMISSION_CREATE, PERMISSION_AUDITOR, AUDIT_MANAGER, AUDIT_VIEWER
)

from .forms import (
    AuditCreateForm,
    GroupAddForm,
    GroupCreateForm,
    GroupEditForm,
    GroupEditMemberForm,
    GroupJoinForm,
    GroupRemoveForm,
    GroupRequestModifyForm,
    PermissionCreateForm,
    PermissionGrantForm,
    PublicKeyForm,
    UsersPublicKeyForm,
)
from ..email_util import cancel_async_emails, send_email, send_async_email
from ..graph import NoSuchUser, NoSuchGroup
from ..models import (
    User, Group, Request, PublicKey, Permission, PermissionMap, AuditLog, GroupEdge, Counter,
    GROUP_JOIN_CHOICES, REQUEST_STATUS_CHOICES, GROUP_EDGE_ROLES, OBJ_TYPES,
    get_all_groups, get_all_users,
    get_user_or_group, Audit, AuditMember, AUDIT_STATUS_CHOICES, AuditLogCategory,
)
from .settings import settings
from .util import ensure_audit_security, GrouperHandler, Alert, test_reserved_names
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
        self.handle_refresh()
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

        if user.id == self.current_user.id:
            num_pending_requests = self.current_user.my_requests_aggregate().count()
        else:
            num_pending_requests = None

        try:
            user_md = self.graph.get_user_details(user.name)
        except NoSuchUser:
            # Either user is probably very new, so they have no metadata yet, or
            # they're disabled, so we've excluded them from the in-memory graph.
            user_md = {}

        open_audits = user.my_open_audits()
        groups = user.my_groups()
        public_keys = user.my_public_keys()
        permissions = user_md.get('permissions', [])
        log_entries = user.my_log_entries()
        self.render("user.html", user=user, groups=groups, public_keys=public_keys,
                    can_control=can_control, permissions=permissions,
                    log_entries=log_entries, num_pending_requests=num_pending_requests,
                    open_audits=open_audits)


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

        # No explicit refresh because handler queries SQL.
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

        # No explicit refresh because handler queries SQL.
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

        # No explicit refresh because handler queries SQL.
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

        return self.redirect("/groups/{}?refresh=yes".format(group.name))


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

        return self.redirect('/groups/{}?refresh=yes'.format(group.name))


class PermissionsView(GrouperHandler):
    '''
    Controller for viewing the major permissions list. There is no privacy here; the existence of
    a permission is public.
    '''
    def get(self, audited_only=False):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        audited_only = bool(int(self.get_argument("audited", 0)))
        if limit > 9000:
            limit = 9000

        permissions = self.graph.get_permissions(audited=audited_only)
        total = len(permissions)
        permissions = permissions[offset:offset + limit]

        can_create = self.current_user.my_creatable_permissions()

        self.render(
            "permissions.html", permissions=permissions, offset=offset, limit=limit, total=total,
            can_create=can_create, audited_permissions=audited_only
        )


class PermissionView(GrouperHandler):
    def get(self, name=None):
        # TODO: use cached data instead, add refresh to appropriate redirects.
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
        # TODO: use cached users instead.
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


class UsersPublicKey(GrouperHandler):
    @ensure_audit_security(u'public_keys')
    def get(self):
        form = UsersPublicKeyForm(self.request.arguments)

        user_key_list = self.session.query(
            PublicKey,
            User,
        ).filter(
            User.id == PublicKey.user_id,
        )

        if not form.validate():
            user_key_list = user_key_list.filter(User.enabled == bool(form.enabled.default))

            total = user_key_list.count()
            user_key_list = user_key_list.offset(form.offset.default).limit(form.limit.default)

            return self.render("users-publickey.html", user_key_list=user_key_list, total=total,
                    form=form, alerts=self.get_form_alerts(form.errors))

        user_key_list = user_key_list.filter(User.enabled == bool(form.enabled.data))

        if form.fingerprint.data:
            user_key_list = user_key_list.filter(PublicKey.fingerprint == form.fingerprint.data)

        if form.sort_by.data == "size":
            user_key_list = user_key_list.order_by(PublicKey.key_size.desc())
        elif form.sort_by.data == "type":
            user_key_list = user_key_list.order_by(PublicKey.key_type.desc())
        elif form.sort_by.data == "age":
            user_key_list = user_key_list.order_by(PublicKey.created_on.asc())
        elif form.sort_by.data == "user":
            user_key_list = user_key_list.order_by(User.username.desc())

        total = user_key_list.count()
        user_key_list = user_key_list.offset(form.offset.data).limit(form.limit.data)

        self.render("users-publickey.html", user_key_list=user_key_list, total=total, form=form)


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

        return self.redirect("/users/{}?refresh=yes".format(user.name))


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

        return self.redirect("/users/{}?refresh=yes".format(user.name))


class UserRequests(GrouperHandler):
    """Handle list all pending requests for a single user."""
    def get(self):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        if limit > 9000:
            limit = 9000

        requests = self.current_user.my_requests_aggregate().order_by(Request.requested_at.desc())

        total = requests.count()
        requests = requests.offset(offset).limit(limit)

        self.render("user-requests.html", requests=requests, offset=offset, limit=limit,
                total=total)


class GroupView(GrouperHandler):
    def get(self, group_id=None, name=None):
        self.handle_refresh()
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
            statuses=AUDIT_STATUS_CHOICES,
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

        return self.redirect("/groups/{}?refresh=yes".format(group.name))


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

        form = GroupRequestModifyForm(self.request.arguments)
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

        edge = self.session.query(GroupEdge).filter_by(
            id=request.edge_id
        ).one()
        if form.data['status'] == 'actioned':
            send_email(
                self.session,
                [request.requester.name],
                'Added to group: {}'.format(group.groupname),
                'request_actioned',
                settings,
                {
                    'group': group.name,
                    'actioned_by': self.current_user.name,
                    'reason': form.data['reason'],
                    'expiration': edge.expiration,
                    'role': edge.role,
                }
            )
        elif form.data['status'] == 'cancelled':
            send_email(
                self.session,
                [request.requester.name],
                'Request to join cancelled: {}'.format(group.groupname),
                'request_cancelled',
                settings,
                {
                    'group': group.name,
                    'cancelled_by': self.current_user.name,
                    'reason': form.data['reason'],
                    'expiration': edge.expiration,
                    'role': edge.role,
                }
            )

        # No explicit refresh because handler queries SQL.
        if form.data['redirect_aggregate']:
            return self.redirect("/user/requests")
        else:
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


class AuditsComplete(GrouperHandler):
    def post(self, audit_id):
        user = self.get_current_user()
        if not user.has_permission(PERMISSION_AUDITOR):
            return self.forbidden()

        audit = self.session.query(Audit).filter(Audit.id == audit_id).one()

        # only owners can complete
        owner_ids = {member.id for member in audit.group.my_owners().values()}
        if user.id not in owner_ids:
            return self.forbidden()

        if audit.complete:
            return self.redirect("/groups/{}".format(audit.group.name))

        edges = {}
        for argument in self.request.arguments:
            if argument.startswith('audit_'):
                edges[int(argument.split('_')[1])] = self.request.arguments[argument][0]

        for member in audit.my_members():
            if member.id in edges:
                # You can only approve yourself (otherwise you can remove yourself
                # from the group and leave it ownerless)
                if member.member.id == user.id:
                    member.status = "approved"
                elif edges[member.id] in AUDIT_STATUS_CHOICES:
                    member.status = edges[member.id]

        self.session.commit()

        # Now if it's completable (no pendings) then mark it complete, else redirect them
        # to the group page.
        if not audit.completable:
            return self.redirect('/groups/{}'.format(audit.group.name))

        # Complete audits have to be "enacted" now. This means anybody marked as remove has to
        # be removed from the group now.
        for member in audit.my_members():
            if member.status == "remove":
                audit.group.revoke_member(self.current_user, member.member,
                                          "Revoked as part of audit.")
                AuditLog.log(self.session, self.current_user.id, 'remove_member',
                             'Removed membership in audit: {}'.format(member.member.name),
                             on_group_id=audit.group.id, category=AuditLogCategory.audit)

        audit.complete = True
        self.session.commit()

        # Now cancel pending emails
        cancel_async_emails(self.session, 'audit-{}'.format(audit.group.id))

        AuditLog.log(self.session, self.current_user.id, 'complete_audit',
                     'Completed group audit.', on_group_id=audit.group.id,
                     category=AuditLogCategory.audit)

        # check if all audits are complete
        if get_audits(self.session, only_open=True).count() == 0:
            AuditLog.log(self.session, self.current_user.id, 'complete_global_audit',
                    'last open audit have been completed', category=AuditLogCategory.audit)

        return self.redirect('/groups/{}'.format(audit.group.name))


class AuditsCreate(GrouperHandler):
    def get(self):
        user = self.get_current_user()
        if not user.has_permission(AUDIT_MANAGER):
            return self.forbidden()

        self.render(
            "audit-create.html", form=AuditCreateForm(),
        )

    def post(self):
        form = AuditCreateForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "audit-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        user = self.get_current_user()
        if not user.has_permission(AUDIT_MANAGER):
            return self.forbidden()

        # Step 1, detect if there are non-completed audits and fail if so.
        open_audits = self.session.query(Audit).filter(
            Audit.complete == False).all()
        if open_audits:
            raise Exception("Sorry, there are audits in progress.")
        ends_at = datetime.strptime(form.data["ends_at"], "%m/%d/%Y")

        # Step 2, find all audited groups and schedule audits for each.
        audited_groups = []
        for groupname in self.graph.groups:
            if not self.graph.get_group_details(groupname)["audited"]:
                continue
            group = Group.get(self.session, name=groupname)
            audit = Audit(
                group_id=group.id,
                ends_at=ends_at,
            )
            try:
                audit.add(self.session)
                self.session.flush()
            except IntegrityError:
                self.session.rollback()
                raise Exception("Failed to start the audit. Please try again.")

            # Update group with new audit
            audited_groups.append(group)
            group.audit_id = audit.id

            # Step 3, now get all members of this group and set up audit rows for those edges.
            for member in group.my_members().values():
                auditmember = AuditMember(
                    audit_id=audit.id, edge_id=member.edge_id
                )
                try:
                    auditmember.add(self.session)
                except IntegrityError:
                    self.session.rollback()
                    raise Exception("Failed to start the audit. Please try again.")

        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'start_audit',
                     'Started global audit.', category=AuditLogCategory.audit)

        # Calculate schedule of emails, basically we send emails at various periods in advance
        # of the end of the audit period.
        schedule_times = []
        not_before = datetime.utcnow() + timedelta(1)
        for days_prior in (28, 21, 14, 7, 3, 1):
            email_time = ends_at - timedelta(days_prior)
            email_time.replace(hour=17, minute=0, second=0)
            if email_time > not_before:
                schedule_times.append((days_prior, email_time))

        # Now send some emails. We do this separately/later to ensure that the audits are all
        # created. Email notifications are sent multiple times if group audits are still
        # outstanding.
        for group in audited_groups:
            mail_to = [
                member.name
                for member in group.my_users()
                if GROUP_EDGE_ROLES[member.role] in ('owner', 'np-owner')
            ]

            send_email(self.session, mail_to, 'Group Audit: {}'.format(group.name), 'audit_notice',
                    settings, {"group": group.name, "ends_at": ends_at})

            for days_prior, email_time in schedule_times:
                send_async_email(
                    self.session,
                    mail_to,
                    'Group Audit: {} - {} day(s) left'.format(group.name, days_prior),
                    'audit_notice_reminder',
                    settings,
                    {
                        "group": group.name,
                        "ends_at": ends_at,
                        "days_left": days_prior,
                    },
                    email_time,
                    async_key='audit-{}'.format(group.id),
                )

        return self.redirect("/audits")


class AuditsView(GrouperHandler):
    def get(self):
        user = self.get_current_user()
        if not (user.has_permission(AUDIT_VIEWER) or user.has_permission(AUDIT_MANAGER)):
            return self.forbidden()

        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 50))
        if limit > 200:
            limit = 200

        open_filter = self.get_argument("filter", "Open Audits")
        audits = get_audits(self.session, only_open=(open_filter == "Open Audits"))

        open_audits = any([not audit.complete for audit in audits])
        total = audits.count()
        audits = audits.offset(offset).limit(limit).all()

        open_audits = self.session.query(Audit).filter(
            Audit.complete == False).all()
        can_start = user.has_permission(AUDIT_MANAGER)

        # FIXME(herb): make limit selected from ui
        audit_log_entries = AuditLog.get_entries(self.session, category=AuditLogCategory.audit,
                limit=100)

        self.render(
            "audits.html", audits=audits, open_filter=open_filter, can_start=can_start,
            offset=offset, limit=limit, total=total, open_audits=open_audits,
            audit_log_entries=audit_log_entries,
        )


class GroupsView(GrouperHandler):
    def get(self):
        self.handle_refresh()
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
        groups = groups[offset:offset + limit]

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

        return self.redirect("/groups/{}?refresh=yes".format(group.name))


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

        # Ensure this doesn't violate auditing constraints
        fail_message = 'This join is denied with this role at this time.'
        try:
            user_can_join = assert_can_join(group, member, role=form.data["role"])
        except UserNotAuditor as e:
            user_can_join = False
            fail_message = e
        if not user_can_join:
            form.member.errors.append(fail_message)

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

        if member.type == "User":
            send_email(
                self.session,
                [member.name],
                'Added to group: {}'.format(group.name),
                'request_actioned',
                settings,
                {
                    'group': group.name,
                    'actioned_by': self.current_user.name,
                    'reason': form.data['reason'],
                    'expiration': expiration,
                    'role': form.data['role'],
                }
            )

        return self.redirect("/groups/{}?refresh=yes".format(group.name))


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
        return self.redirect("/groups/{}?refresh=yes".format(group.name))


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

        if group.canjoin == "nobody":
            fail_message = 'This group cannot be joined at this time.'
            return self.render(
                "group-join.html", form=form, group=group,
                alerts=[
                    Alert('danger', fail_message)
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

            email_context = {
                    "requester": member.name,
                    "requested_by": self.current_user.name,
                    "requested": group.name,
                    "reason": form.data["reason"],
                    "expiration": expiration,
                    "role": form.data["role"],
                    }
            send_email(self.session, mail_to, 'Request to join: {}'.format(group.name),
                    'pending_request', settings, email_context)

        elif group.canjoin == 'canjoin':
            AuditLog.log(self.session, self.current_user.id, 'join_group',
                         '{} auto-approved to join with role: {}'.format(
                             member.name, form.data["role"]),
                         on_group_id=group.id)
        else:
            raise Exception('Need to update the GroupJoin.post audit logging')

        return self.redirect("/groups/{}?refresh=yes".format(group.name))

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

        return self.redirect("/groups/{}?refresh=yes".format(group.name))


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

        return self.redirect("/groups/{}?refresh=yes".format(group.name))


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

        if group.audit:
            # complete the audit
            group.audit.complete = True
            self.session.commit()

            AuditLog.log(self.session, self.current_user.id, 'complete_audit',
                         'Disabling group completes group audit.', on_group_id=group.id)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))


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

        try:
            pubkey = public_key.add_public_key(self.session, user, form.data["public_key"])
        except public_key.PublicKeyParseError:
            form.public_key.errors.append(
                "Key failed to parse and is invalid."
            )
            return self.render(
                "public-key-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )
        except public_key.DuplicateKey:
            form.public_key.errors.append(
                "Key already in use. Public keys must be unique."
            )
            return self.render(
                "public-key-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        AuditLog.log(self.session, self.current_user.id, 'add_public_key',
                     'Added public key: {}'.format(pubkey.fingerprint),
                     on_user_id=user.id)

        email_context = {
                "actioner": self.current_user.name,
                "changed_user": user.name,
                "action": "added",
                }
        send_email(self.session, [user.name], 'Public SSH key added', 'ssh_keys_changed',
                settings, email_context)

        return self.redirect("/users/{}?refresh=yes".format(user.name))


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

        email_context = {
                "actioner": self.current_user.name,
                "changed_user": user.name,
                "action": "removed",
                }
        send_email(self.session, [user.name], 'Public SSH key removed', 'ssh_keys_changed',
                settings, email_context)

        return self.redirect("/users/{}?refresh=yes".format(user.name))


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


class NotFound(GrouperHandler):
    def get(self):
        return self.notfound()


# Don't use GraphHandler here as we don't want to count
# these as requests.
class Stats(RequestHandler):
    def get(self):
        return self.write(stats.to_dict())


class PerfProfile(RequestHandler):
    def get(self, trace_uuid):
        from grouper.models import Session
        try:
            flamegraph_svg = perf_profile.get_flamegraph_svg(Session(), trace_uuid)
        except perf_profile.InvalidUUID:
            pass
        else:
            self.set_header("Content-Type", "image/svg+xml")
            self.write(flamegraph_svg)
