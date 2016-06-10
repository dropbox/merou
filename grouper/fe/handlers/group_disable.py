from grouper.fe.util import GrouperHandler
from grouper.model_soup import Group
from grouper.models.audit_log import AuditLog
from grouper.service_account import is_service_account
from grouper.user import user_role


class GroupDisable(GrouperHandler):
    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not user_role(self.current_user, members) in ("owner", "np-owner"):
            return self.forbidden()

        # Enabling and disabling service accounts via the group endpoints is forbidden
        # because we need the preserve_membership data that is only available via the
        # UserEnable form.
        if is_service_account(self.session, group=group):
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
