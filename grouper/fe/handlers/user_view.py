from grouper.constants import USER_METADATA_SHELL_KEY
from grouper.fe.handlers.user_disable import UserDisable
from grouper.fe.handlers.user_enable import UserEnable
from grouper.fe.util import GrouperHandler
from grouper.graph import NoSuchUser
from grouper.models.user import User
from grouper.permissions import get_requests_by_owner
from grouper.public_key import (get_public_key_permissions, get_public_key_tags,
    get_public_keys_of_user)
from grouper.user import get_log_entries_by_user, user_open_audits, user_requests_aggregate
from grouper.user_group import get_groups_by_user
from grouper.user_metadata import get_user_metadata_by_key
from grouper.user_password import user_passwords
from grouper.user_permissions import user_is_user_admin


class UserView(GrouperHandler):

    @staticmethod
    def get_template_vars(session, actor, user, graph):
        ret = {}
        ret["can_control"] = (user.name == actor.name or user_is_user_admin(session, actor))
        ret["can_disable"] = UserDisable.check_access(session, actor, user)
        ret["can_enable"] = UserEnable.check_access(session, actor, user)

        if user.id == actor.id:
            ret["num_pending_group_requests"] = user_requests_aggregate(session, actor).count()
            _, ret["num_pending_perm_requests"] = get_requests_by_owner(session, actor,
                 status='pending', limit=1, offset=0)
        else:
            ret["num_pending_group_requests"] = None
            ret["num_pending_perm_requests"] = None

        try:
            user_md = graph.get_user_details(user.name)
        except NoSuchUser:
            # Either user is probably very new, so they have no metadata yet, or
            # they're disabled, so we've excluded them from the in-memory graph.
            user_md = {}

        shell = (get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY).data_value
            if get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY)
            else "No shell configured")
        ret["shell"] = shell
        ret["open_audits"] = user_open_audits(session, user)
        group_edge_list = get_groups_by_user(session, user) if user.enabled else []
        ret["groups"] = [{'name': g.name, 'type': 'Group', 'role': ge._role}
            for g, ge in group_edge_list]
        ret["passwords"] = user_passwords(session, user)
        ret["public_keys"] = get_public_keys_of_user(session, user.id)
        for key in ret["public_keys"]:
            key.tags = get_public_key_tags(session, key)
            key.pretty_permissions = ["{} ({})".format(perm.name,
               perm.argument if perm.argument else "unargumented")
               for perm in get_public_key_permissions(session, key)]
        ret["permissions"] = user_md.get('permissions', [])
        ret["log_entries"] = get_log_entries_by_user(session, user)

        return ret

    def get(self, user_id=None, name=None):
        self.handle_refresh()
        user = User.get(self.session, user_id, name)
        if user_id is not None:
            user = self.session.query(User).filter_by(id=user_id).scalar()
        else:
            user = self.session.query(User).filter_by(username=name).scalar()

        if not user:
            return self.notfound()

        if user.role_user:
            return self.redirect("/service/{}".format(user_id or name))

        self.render("user.html",
                    user=user,
                    **self.get_template_vars(self.session, self.current_user, user, self.graph)
                    )
