from sqlalchemy.exc import IntegrityError
from grouper.fe.forms import TagCreateForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.public_key_tag import PublicKeyTag


class TagsView(GrouperHandler):
    def get(self):
        self.handle_refresh()
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        if limit > 9000:
            limit = 9000

        tags = self.session.query(PublicKeyTag).all()
        total = len(tags)
        tags = tags[offset:offset + limit]

        form = TagCreateForm()

        self.render(
            "tags.html", tags=tags, form=form,
            offset=offset, limit=limit, total=total,
        )

    def post(self):
        form = TagCreateForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "tag-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        tag = PublicKeyTag(
            name=form.data["tagname"],
            description=form.data["description"],
        )

        try:
            tag.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.tagname.errors.append(
                "{} already exists".format(form.data["tagname"])
            )
            return self.render(
                "tag-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'create_tag',
                     'Created new tag.', on_tag_id=tag.id)

        return self.redirect("/tags/{}?refresh=yes".format(tag.name))
