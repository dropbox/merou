from grouper.fe.util import Alert, GrouperHandler
from grouper.graph import NoSuchGroup
from grouper.model_soup import (APPROVER_ROLE_INDICIES, AUDIT_STATUS_CHOICES,
        Group, OWNER_ROLE_INDICES)
from grouper.permissions import get_owner_arg_list, get_pending_request_by_group
from grouper.service_account import is_service_account
from grouper.user import user_role, user_role_index
from grouper.user_permissions import user_grantable_permissions


class GroupView(GrouperHandler):
    def get(self, group_id=None, name=None):
        self.handle_refresh()
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if is_service_account(self.session, group=group):
            return self.redirect("/service/{}".format(group.groupname))

        grantable = user_grantable_permissions(self.session, self.current_user)

        try:
            group_md = self.graph.get_group_details(group.name)
        except NoSuchGroup:
            # Very new group with no metadata yet, or it has been disabled and
            # excluded from in-memory cache.
            group_md = {}

        members = group.my_members()
        groups = group.my_groups()
        permissions = group_md.get('permissions', [])

        permission_requests_pending = []
        for req in get_pending_request_by_group(self.session, group):
            granters = []
            for owner, argument in get_owner_arg_list(self.session, req.permission, req.argument):
                granters.append(owner.name)
            permission_requests_pending.append((req, granters))

        audited = group_md.get('audited', False)
        log_entries = group.my_log_entries()
        num_pending = group.my_requests("pending").count()
        current_user_role = {
            'is_owner': user_role_index(self.current_user, members) in OWNER_ROLE_INDICES,
            'is_approver': user_role_index(self.current_user, members) in APPROVER_ROLE_INDICIES,
            'is_manager': user_role(self.current_user, members) == "manager",
            'is_member': user_role(self.current_user, members) is not None,
            'role': user_role(self.current_user, members),
            }
        can_leave = current_user_role['is_member'] and not current_user_role['is_owner']

        # Add mapping_id to permissions structure
        my_permissions = group.my_permissions()
        for perm_up in permissions:
            for perm_direct in my_permissions:
                if (perm_up['permission'] == perm_direct.name and
                        perm_up['argument'] == perm_direct.argument):
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
            statuses=AUDIT_STATUS_CHOICES, current_user_role=current_user_role,
            permission_requests_pending=permission_requests_pending, can_leave=can_leave,
        )
