from grouper.fe.forms import UsersUserTokenForm
from grouper.fe.util import ensure_audit_security, GrouperHandler
from grouper.model_soup import User
from grouper.models.user_token import UserToken


class UsersUserTokens(GrouperHandler):
    @ensure_audit_security(u'user_tokens')
    def get(self):
        form = UsersUserTokenForm(self.request.arguments)

        user_token_list = self.session.query(
            UserToken,
            User,
        ).filter(
            User.id == UserToken.user_id,
        )

        if not form.validate():
            total = user_token_list.count()

            return self.render(
                "users-usertokens.html",
                user_token_list=user_token_list,
                total=total,
                form=form,
                alerts=self.get_form_alerts(form.errors),
            )

        user_token_list = user_token_list.filter(User.enabled == bool(form.enabled.data))

        if form.sort_by.data == "name":
            user_token_list = user_token_list.order_by(UserToken.name.desc())
        elif form.sort_by.data == "age":
            user_token_list = user_token_list.order_by(UserToken.created_at.asc())
        elif form.sort_by.data == "user":
            user_token_list = user_token_list.order_by(User.username.desc())

        total = user_token_list.count()
        user_token_list = user_token_list.offset(form.offset.data).limit(form.limit.data)

        self.render(
            "users-usertokens.html",
            user_token_list=user_token_list,
            total=total,
            form=form,
        )
