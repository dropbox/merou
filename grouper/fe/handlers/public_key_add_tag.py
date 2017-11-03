from grouper.fe.forms import PublicKeyAddTagForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.public_key_tag import PublicKeyTag
from grouper.models.user import User
from grouper.public_key import add_tag_to_public_key, DuplicateTag, get_public_key, KeyNotFound
from grouper.role_user import can_manage_role_user
from grouper.user_permissions import user_is_user_admin


class PublicKeyAddTag(GrouperHandler):

    @staticmethod
    def check_access(session, actor, target):
        return (actor.name == target.name or user_is_user_admin(session, actor) or
            (target.role_user and can_manage_role_user(session, actor, tuser=target)))

    def get(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        try:
            key = get_public_key(self.session, user.id, key_id)
        except KeyNotFound:
            return self.notfound()

        form = PublicKeyAddTagForm()
        form.tagname.choices = []
        for tag in self.session.query(PublicKeyTag).filter_by(enabled=True).all():
            form.tagname.choices.append([tag.name, tag.name])

        self.render("public-key-add-tag.html", user=user, key=key, form=form)

    def post(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        try:
            key = get_public_key(self.session, user.id, key_id)
        except KeyNotFound:
            return self.notfound()

        form = PublicKeyAddTagForm(self.request.arguments)
        form.tagname.choices = []
        for tag in self.session.query(PublicKeyTag).filter_by(enabled=True).all():
            form.tagname.choices.append([tag.name, tag.name])

        if not form.validate():
            return self.render(
                "public-key-add-tag.html", form=form, user=user, key=key,
                alerts=self.get_form_alerts(form.errors)
            )

        tag = PublicKeyTag.get(self.session, name=form.data["tagname"])

        if not tag:
            form.tagname.errors.append("Unknown tag name {}".format(form.data["tagname"]))
            return self.render(
                "public-key-add-tag.html", form=form, user=user, key=key,
                alerts=self.get_form_alerts(form.errors)
            )

        try:
            add_tag_to_public_key(self.session, key, tag)
        except DuplicateTag:
            return self.render(
                "public-key-add-tag.html", form=form, user=user, key=key,
                alerts=["This key already has that tag!"]
            )

        AuditLog.log(self.session, self.current_user.id, 'tag_public_key',
                     'Tagged public key: {}'.format(key.fingerprint),
                     on_tag_id=tag.id, on_user_id=user.id)

        return self.redirect("/users/{}?refresh=yes".format(user.name))
