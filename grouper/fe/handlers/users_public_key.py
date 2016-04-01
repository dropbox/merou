from grouper.fe.forms import UsersPublicKeyForm
from grouper.fe.util import ensure_audit_security, GrouperHandler
from grouper.model_soup import User
from grouper.models.public_key import PublicKey


class UsersPublicKey(GrouperHandler):
    @ensure_audit_security(u'public_keys')
    def get(self):
        form = UsersPublicKeyForm(self.request.arguments)

        user_key_list = self.session.query(
            PublicKey,
            User,
        ).filter(
            User.id == PublicKey.user_id,
        )

        if not form.validate():
            user_key_list = user_key_list.filter(User.enabled == bool(form.enabled.default))

            total = user_key_list.count()
            user_key_list = user_key_list.offset(form.offset.default).limit(form.limit.default)

            return self.render("users-publickey.html", user_key_list=user_key_list, total=total,
                    form=form, alerts=self.get_form_alerts(form.errors))

        user_key_list = user_key_list.filter(User.enabled == bool(form.enabled.data))

        if form.fingerprint.data:
            user_key_list = user_key_list.filter(PublicKey.fingerprint == form.fingerprint.data)

        if form.sort_by.data == "size":
            user_key_list = user_key_list.order_by(PublicKey.key_size.desc())
        elif form.sort_by.data == "type":
            user_key_list = user_key_list.order_by(PublicKey.key_type.desc())
        elif form.sort_by.data == "age":
            user_key_list = user_key_list.order_by(PublicKey.created_on.asc())
        elif form.sort_by.data == "user":
            user_key_list = user_key_list.order_by(User.username.desc())

        total = user_key_list.count()
        user_key_list = user_key_list.offset(form.offset.data).limit(form.limit.data)

        self.render("users-publickey.html", user_key_list=user_key_list, total=total, form=form)
