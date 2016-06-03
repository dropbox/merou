from grouper.fe.util import GrouperHandler
from grouper.model_soup import User
from grouper.models.audit_log import AuditLog
from grouper.public_key import get_public_key, KeyNotFound, add_tag_to_public_key, DuplicateTag
from grouper.fe.forms import PublicKeyAddTagForm
from grouper.models.public_key_tag import PublicKeyTag


class PublicKeyAddTag(GrouperHandler):
    def get(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        try:
            key = get_public_key(self.session, user.id, key_id)
        except KeyNotFound:
            return self.notfound()

        form = PublicKeyAddTagForm()
        for tag in self.session.query(PublicKeyTag).all():
            form.tagname.choices.append([tag.name, tag.name])

        self.render("public-key-add-tag.html", user=user, key=key, form=form)

    def post(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        try:
            key = get_public_key(self.session, user.id, key_id)
        except KeyNotFound:
            return self.notfound()

        form = PublicKeyAddTagForm(self.request.arguments)
        for tag in self.session.query(PublicKeyTag).all():
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
