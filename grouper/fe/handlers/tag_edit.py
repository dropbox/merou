from sqlalchemy.exc import IntegrityError
from grouper.fe.forms import TagEditForm
from grouper.fe.util import GrouperHandler
from grouper.models.counter import Counter
from grouper.models.audit_log import AuditLog
from grouper.models.public_key_tag import PublicKeyTag
from grouper.constants import TAG_EDIT


class TagEdit(GrouperHandler):
    def get(self, tag_id=None, name=None):
        tag = PublicKeyTag.get(self.session, tag_id, name)
        if not tag:
            return self.notfound()

        if not self.current_user.has_permission(TAG_EDIT, tag.name):
            return self.forbidden()

        form = TagEditForm(obj=tag)

        self.render("tag-edit.html", tag=tag, form=form)

    def post(self, tag_id=None, name=None):
        tag = PublicKeyTag.get(self.session, tag_id, name)
        if not tag:
            return self.notfound()

        if not self.current_user.has_permission(TAG_EDIT, tag.name):
            return self.forbidden()

        form = TagEditForm(self.request.arguments, obj=tag)
        if not form.validate():
            return self.render(
                "tag-edit.html", tag=tag, form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        tag.description = form.data["description"]
        Counter.incr(self.session, "updates")

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            form.tagname.errors.append(
                "{} already exists".format(form.data["tagname"])
            )
            return self.render(
                "tag-edit.html", tag=tag, form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        AuditLog.log(self.session, self.current_user.id, 'edit_tag',
                     'Edited tag.', on_tag_id=tag.id)

        return self.redirect("/tags/{}".format(tag.name))
