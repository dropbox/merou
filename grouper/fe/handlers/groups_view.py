from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from grouper.fe.forms import GroupCreateForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group

if TYPE_CHECKING:
    from typing import Any, Set


class GroupsView(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        self.handle_refresh()
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        enabled = bool(int(self.get_argument("enabled", 1)))
        audited_only = bool(int(self.get_argument("audited", 0)))
        if limit > 9000:
            limit = 9000

        if not enabled:
            groups = self.graph.get_disabled_groups()
            directly_audited_groups = set()  # type: Set[str]
        elif audited_only:
            groups = self.graph.get_groups(audited=True)
            directly_audited_groups = set(
                [g.name for g in self.graph.get_groups(directly_audited=True)]
            )
        else:
            groups = self.graph.get_groups()
            directly_audited_groups = set()
        groups = [group for group in groups if not group.is_role_user]
        total = len(groups)
        groups = groups[offset : offset + limit]

        form = GroupCreateForm()

        self.render(
            "groups.html",
            groups=groups,
            form=form,
            offset=offset,
            limit=limit,
            total=total,
            audited_groups=audited_only,
            directly_audited_groups=directly_audited_groups,
            enabled=enabled,
        )

    def post(self, *args: Any, **kwargs: Any) -> None:
        form = GroupCreateForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "group-create.html", form=form, alerts=self.get_form_alerts(form.errors)
            )

        if "@" in form.data["groupname"]:
            form.groupname.errors.append("Group names cannot contain @")
            return self.render(
                "group-create.html", form=form, alerts=self.get_form_alerts(form.errors)
            )

        group = Group(
            groupname=form.data["groupname"],
            description=form.data["description"],
            canjoin=form.data["canjoin"],
            auto_expire=form.data["auto_expire"],
            require_clickthru_tojoin=form.data["require_clickthru_tojoin"],
        )
        try:
            group.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.groupname.errors.append("{} already exists".format(form.data["groupname"]))
            return self.render(
                "group-create.html", form=form, alerts=self.get_form_alerts(form.errors)
            )

        group.add_member(
            self.current_user,
            self.current_user,
            "Group Creator",
            "actioned",
            None,
            form.data["creatorrole"],
        )
        self.session.commit()

        AuditLog.log(
            self.session,
            self.current_user.id,
            "create_group",
            "Created new group.",
            on_group_id=group.id,
        )

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
