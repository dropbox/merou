from grouper import group as group_biz
from grouper.constants import USER_METADATA_SHELL_KEY
from grouper.fe.handlers.user_disable import UserDisable
from grouper.fe.handlers.user_enable import UserEnable
from grouper.fe.util import GrouperHandler
from grouper.graph import NoSuchUser, NoSuchGroup
from grouper.model_soup import (User, Group, APPROVER_ROLE_INDICIES, AUDIT_STATUS_CHOICES,
        OWNER_ROLE_INDICES)
from grouper.permissions import get_requests_by_owner
from grouper.public_key import get_public_keys_of_user
from grouper.user import user_open_audits, user_requests_aggregate, user_grantable_permissions, user_role, user_role_index
from grouper.user_metadata import get_user_metadata_by_key


class ServiceAccountView(GrouperHandler):
    def get(self, user_id=None, name=None):
        print("HELOO")
        self.handle_refresh()
        user = User.get(self.session, user_id, name)
        if user_id is not None:
            user = self.session.query(User).filter_by(id=user_id).scalar()
        else:
            user = self.session.query(User).filter_by(username=name).scalar()

        if not user:
            return self.notfound()

        if not user.role_user:
            return self.notfound()

        can_control = user.name == self.current_user.name or self.current_user.user_admin
        can_disable = UserDisable.check_access(self.session, self.current_user, user)
        can_enable = UserEnable.check_access(self.session, self.current_user, user)

        if user.id == self.current_user.id:
            num_pending_group_requests = user_requests_aggregate(self.session,
                 self.current_user).count()
            _, num_pending_perm_requests = get_requests_by_owner(self.session, self.current_user,
                 status='pending', limit=1, offset=0)
        else:
            num_pending_group_requests = None
            num_pending_perm_requests = None

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

        members = group.my_members()
        open_audits = user_open_audits(self.session, user)
        group_edge_list = group_biz.get_groups_by_user(self.session, user) if user.enabled else []
        groups = [{'name': g.name, 'type': 'Group', 'role': ge._role} for g, ge in group_edge_list]
        public_keys = get_public_keys_of_user(self.session, user.id)
        permissions = user_md.get('permissions', [])
        log_entries = user.my_log_entries()
        current_user_role = {
            'is_owner': user_role_index(self.current_user, members) in OWNER_ROLE_INDICES,
            'is_approver': user_role_index(self.current_user, members) in APPROVER_ROLE_INDICIES,
            'is_manager': user_role(self.current_user, members) == "manager",
            'role': user_role(self.current_user, members),
        }
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
                    )
