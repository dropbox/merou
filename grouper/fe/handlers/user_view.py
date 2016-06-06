from grouper import group as group_biz
from grouper.constants import SHELL_MD_KEY
from grouper.fe.handlers.user_disable import UserDisable
from grouper.fe.handlers.user_enable import UserEnable
from grouper.fe.util import GrouperHandler
from grouper.graph import NoSuchUser
from grouper.model_soup import User
from grouper.permissions import get_requests_by_owner


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

        can_control = user.name == self.current_user.name or self.current_user.user_admin
        can_disable = UserDisable.check_access(self.current_user, user)
        can_enable = UserEnable.check_access(self.current_user, user)

        if user.id == self.current_user.id:
            num_pending_group_requests = self.current_user.my_requests_aggregate().count()
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

        shell = (user.get_metadata(SHELL_MD_KEY).data_value if user.get_metadata(SHELL_MD_KEY)
            else "No shell configured")
        open_audits = user.my_open_audits()
        group_edge_list = group_biz.get_groups_by_user(self.session, user) if user.enabled else []
        groups = [{'name': g.name, 'type': 'Group', 'role': ge._role} for g, ge in group_edge_list]
        public_keys = user.my_public_keys()
        permissions = user_md.get('permissions', [])
        log_entries = user.my_log_entries()
        self.render("user.html",
                    user=user,
                    groups=groups,
                    public_keys=public_keys,
                    can_control=can_control,
                    permissions=permissions,
                    can_disable=can_disable,
                    can_enable=can_enable,
                    user_tokens=user.tokens,
                    log_entries=log_entries,
                    num_pending_group_requests=num_pending_group_requests,
                    num_pending_perm_requests=num_pending_perm_requests,
                    open_audits=open_audits,
                    shell=shell,
                    )
