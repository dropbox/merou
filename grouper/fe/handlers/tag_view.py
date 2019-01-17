from grouper.constants import TAG_EDIT
from grouper.fe.util import GrouperHandler
from grouper.models.public_key_tag import PublicKeyTag
from grouper.permissions import get_all_enabled_permissions
from grouper.public_key import get_public_key_tag_permissions
from grouper.user_permissions import user_has_permission


class TagView(GrouperHandler):
    def get(self, tag_id=None, name=None):
        self.handle_refresh()
        tag = PublicKeyTag.get(self.session, tag_id, name)
        if not tag:
            return self.notfound()

        permissions = get_public_key_tag_permissions(self.session, tag)
        log_entries = tag.my_log_entries()
        is_owner = user_has_permission(self.session, self.current_user, TAG_EDIT, tag.name)
        can_grant = get_all_enabled_permissions(self.session) if is_owner else []

        self.render(
            "tag.html", tag=tag, permissions=permissions, can_grant=can_grant,
            log_entries=log_entries, is_owner=is_owner,
        )
