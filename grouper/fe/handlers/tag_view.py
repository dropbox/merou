from grouper.constants import TAG_EDIT
from grouper.fe.util import GrouperHandler
from grouper.model_soup import Permission
from grouper.models.public_key_tag import PublicKeyTag
from grouper.public_key import get_public_key_tag_permissions


class TagView(GrouperHandler):
    def get(self, tag_id=None, name=None):
        self.handle_refresh()
        tag = PublicKeyTag.get(self.session, tag_id, name)
        if not tag:
            return self.notfound()

        permissions = get_public_key_tag_permissions(self.session, tag)
        log_entries = tag.my_log_entries()
        is_owner = self.current_user.has_permission(TAG_EDIT, tag.name)
        can_grant = self.session.query(Permission).all() if is_owner else []

        self.render(
            "tag.html", tag=tag, permissions=permissions, can_grant=can_grant,
            log_entries=log_entries, is_owner=is_owner,
        )
