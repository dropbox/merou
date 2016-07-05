from grouper import group as group_biz
from grouper.constants import USER_METADATA_SHELL_KEY
from grouper.fe.handlers.user_disable import UserDisable
from grouper.fe.handlers.user_enable import UserEnable
from grouper.fe.util import Alert, GrouperHandler
from grouper.graph import NoSuchGroup, NoSuchUser
from grouper.model_soup import (APPROVER_ROLE_INDICIES, AUDIT_STATUS_CHOICES, Group,
    OWNER_ROLE_INDICES, User)
from grouper.permissions import get_pending_request_by_group
from grouper.public_key import get_public_keys_of_user
from grouper.service_account import can_manage_service_account
from grouper.user import get_log_entries_by_user, user_role, user_role_index
from grouper.user_metadata import get_user_metadata_by_key
from grouper.user_permissions import user_grantable_permissions


class ServiceAccountView(GrouperHandler):
    def get(self, user_id=None, name=None):
        self.handle_refresh()
        user = User.get(self.session, user_id, name)

        if not user or not user.role_user:
            return self.notfound()

        can_control = can_manage_service_account(self.session, user=self.current_user, tuser=user)
        can_disable = UserDisable.check_access(self.session, self.current_user, user)
        can_enable = UserEnable.check_access(self.session, self.current_user, user)

        try:
            user_md = self.graph.get_user_details(user.name)
        except NoSuchUser:
            # Either user is probably very new, so they have no metadata yet, or
            # they're disabled, so we've excluded them from the in-memory graph.
            user_md = {}

        shell = (get_user_metadata_by_key(self.session, user.id, USER_METADATA_SHELL_KEY).data_value
            if get_user_metadata_by_key(self.session, user.id, USER_METADATA_SHELL_KEY)
            else "No shell configured")
        group = Group.get(self.session, name=name)

        try:
            group_md = self.graph.get_group_details(group.name)
        except NoSuchGroup:
            # Very new group with no metadata yet, or it has been disabled and
            # excluded from in-memory cache.
            group_md = {}

        grantable = user_grantable_permissions(self.session, self.current_user)
        members = group.my_members()
        group_edge_list = group_biz.get_groups_by_user(self.session, user) if user.enabled else []
        groups = [{'name': g.name, 'type': 'Group', 'role': ge._role} for g, ge in group_edge_list]
        public_keys = get_public_keys_of_user(self.session, user.id)
        permissions = user_md.get('permissions', [])
        # Combine the logs from the User and Group component. Use set to remove any duplicates
        # and sorted to sort the combined logs by log time
        log_entries = sorted(set(get_log_entries_by_user(self.session, user) +
            group.my_log_entries()), key=lambda x: x.log_time, reverse=True)
        current_user_role = {
            'is_owner': user_role_index(self.current_user, members) in OWNER_ROLE_INDICES,
            'is_approver': user_role_index(self.current_user, members) in APPROVER_ROLE_INDICIES,
            'is_manager': user_role(self.current_user, members) == "manager",
            'role': user_role(self.current_user, members),
        }

        permission_requests_pending = get_pending_request_by_group(self.session, group)
        audited = group_md.get('audited', False)
        num_pending = group.my_requests("pending").count()

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

        self.render("service.html",
                    user=user,
                    group=group,
                    members=members,
                    groups=groups,
                    public_keys=public_keys,
                    can_control=can_control,
                    permissions=permissions,
                    can_disable=can_disable,
                    can_enable=can_enable,
                    user_tokens=user.tokens,
                    log_entries=log_entries,
                    shell=shell,
                    current_user_role=current_user_role,
                    num_pending=num_pending,
                    alerts=alerts,
                    grantable=grantable,
                    audited=audited,
                    statuses=AUDIT_STATUS_CHOICES,
                    permission_requests_pending=permission_requests_pending,
                    )
