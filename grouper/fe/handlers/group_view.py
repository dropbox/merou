from grouper.fe.util import Alert, GrouperHandler
from grouper.graph import NoSuchGroup
from grouper.model_soup import (APPROVER_ROLE_INDICIES, AUDIT_STATUS_CHOICES,
        Group, OWNER_ROLE_INDICES)
from grouper.permissions import get_owner_arg_list, get_pending_request_by_group
from grouper.service_account import is_service_account
from grouper.user import user_role, user_role_index
from grouper.user_permissions import user_grantable_permissions


class GroupView(GrouperHandler):

    @staticmethod
    def get_template_vars(session, actor, group, graph):
        ret = {}
        ret["grantable"] = user_grantable_permissions(session, actor)

        try:
            group_md = graph.get_group_details(group.name)
        except NoSuchGroup:
            # Very new group with no metadata yet, or it has been disabled and
            # excluded from in-memory cache.
            group_md = {}

        ret["members"] = group.my_members()
        ret["groups"] = group.my_groups()
        ret["permissions"] = group_md.get('permissions', [])

        ret["permission_requests_pending"] = []
        for req in get_pending_request_by_group(session, group):
            granters = []
            for owner, argument in get_owner_arg_list(session, req.permission, req.argument):
                granters.append(owner.name)
            ret["permission_requests_pending"].append((req, granters))

        ret["audited"] = group_md.get('audited', False)
        ret["log_entries"] = group.my_log_entries()
        ret["num_pending"] = group.my_requests("pending").count()
        ret["current_user_role"] = {
            'is_owner': user_role_index(actor, ret["members"]) in OWNER_ROLE_INDICES,
            'is_approver': user_role_index(actor, ret["members"]) in APPROVER_ROLE_INDICIES,
            'is_manager': user_role(actor, ret["members"]) == "manager",
            'is_member': user_role(actor, ret["members"]) is not None,
            'role': user_role(actor, ret["members"]),
            }
        ret["can_leave"] = (ret["current_user_role"]['is_member'] and not
            ret["current_user_role"]['is_owner'])
        ret["statuses"] = AUDIT_STATUS_CHOICES

        # Add mapping_id to permissions structure
        ret["my_permissions"] = group.my_permissions()
        for perm_up in ret["permissions"]:
            for perm_direct in ret["my_permissions"]:
                if (perm_up['permission'] == perm_direct.name and
                        perm_up['argument'] == perm_direct.argument):
                    perm_up['mapping_id'] = perm_direct.mapping_id
                    break

        ret["alerts"] = []
        ret["self_pending"] = group.my_requests("pending", user=actor).count()
        if ret["self_pending"]:
            ret["alerts"].append(Alert('info', 'You have a pending request to join this group.',
                None))

        return ret

    def get(self, group_id=None, name=None):
        self.handle_refresh()
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if is_service_account(self.session, group=group):
            return self.redirect("/service/{}".format(group.groupname))

        self.render(
            "group.html", group=group,
            **self.get_template_vars(self.session, self.current_user, group, self.graph)
        )
