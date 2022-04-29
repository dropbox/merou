import re
from datetime import datetime, timedelta

from wtforms import (
    BooleanField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
    validators,
)
from wtforms.validators import ValidationError
from wtforms_tornado import Form

from grouper import constants
from grouper.entities.group_edge import GROUP_EDGE_ROLES

GROUP_CANJOIN_CHOICES = [("canjoin", "Anyone"), ("canask", "Must Ask"), ("nobody", "Nobody")]


class ValidateRegex:
    def __init__(self, regex):
        # We assume any regex passed to us does not have line anchors.
        self.regex = r"^" + regex + r"$"
        self._re = re.compile(self.regex)

    def __call__(self, form, field):
        if not self._re.match(field.data):
            raise ValidationError("Field must match '{}'".format(self.regex))


class ValidateDate:
    def __call__(self, form, field):
        try:
            if field.data:
                datetime.strptime(field.data, "%m/%d/%Y")
        except ValueError:
            raise ValidationError("{} does not match format 'MM/DD/YYYY'".format(field.data))


class DaysTimeDeltaField(IntegerField):
    def process_data(self, value):
        """Converts from TimeDelta notation to a simple integer"""
        # Do the check because groups with no expiration will result in value being None
        if hasattr(value, "days"):
            self.data = value.days
        else:
            self.data = None

    def process_formdata(self, valuelist):
        # We need to support None values for groups with no expiration
        if valuelist and valuelist[0]:
            super().process_formdata(valuelist)
            self.data = timedelta(days=self.data)
        else:
            self.data = None


class PublicKeyForm(Form):
    public_key = TextAreaField("Public Key", [validators.DataRequired()])


class PermissionGrantForm(Form):
    permission = SelectField(
        "Permission",
        [validators.DataRequired()],
        choices=[["", "(select one)"]],
        default="",
        description=(
            "Note: The 'arguments' provided in this selector "
            "are not really arguments...they are more like "
            "suggestions.  you still need to type the argument in "
            "the 'Argument' textbox below."
        ),
    )
    argument = StringField(
        "Argument",
        [
            validators.Length(min=0, max=constants.MAX_NAME_LENGTH),
            ValidateRegex(constants.ARGUMENT_VALIDATION),
        ],
    )


class PermissionCreateForm(Form):
    name = StringField(
        "Name",
        [
            validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
            validators.DataRequired(),
            ValidateRegex(constants.PERMISSION_VALIDATION),
        ],
    )
    description = TextAreaField("Description")


class GroupCreateForm(Form):
    creatorrole = SelectField(
        "Creator role",
        choices=[("owner", "Owner"), ("np-owner", "No-Permissions Owner")],
        default="owner",
    )
    groupname = StringField(
        "Name",
        [
            validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
            validators.DataRequired(),
            ValidateRegex(constants.NAME_VALIDATION),
        ],
    )
    email_address = StringField(
        "Group contact email address",
        [validators.Optional(), validators.Length(min=3, max=constants.MAX_NAME_LENGTH)],
    )
    description = TextAreaField("Description")
    canjoin = SelectField("Who Can Join?", choices=GROUP_CANJOIN_CHOICES, default="canask")
    auto_expire = DaysTimeDeltaField("Default Expiration (Days)")
    require_clickthru_tojoin = BooleanField("Require Clickthru", default=False)


class GroupEditForm(Form):
    groupname = StringField(
        "Name",
        [
            validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
            validators.DataRequired(),
            ValidateRegex(constants.NAME_VALIDATION),
        ],
    )
    email_address = StringField(
        "Group contact email address",
        [validators.Optional(), validators.Length(min=3, max=constants.MAX_NAME_LENGTH)],
    )
    description = TextAreaField("Description")
    canjoin = SelectField("Who Can Join?", choices=GROUP_CANJOIN_CHOICES, default="canask")
    auto_expire = DaysTimeDeltaField("Default Expiration (Days)")
    require_clickthru_tojoin = BooleanField("Require Clickthru", default=False)


class AuditCreateForm(Form):
    ends_at = StringField(
        "Ends At", [ValidateDate(), validators.DataRequired()], id="audit-form-ends-at"
    )


class GroupRequestModifyForm(Form):
    # Caller of the form will add choices based on current status.
    status = SelectField("New Status", [validators.DataRequired()])
    reason = TextAreaField("Reason", [validators.DataRequired()])
    redirect_aggregate = HiddenField()


class GroupAddForm(Form):
    # Caller of the form will add choices for member and role.
    member = SelectField(
        "Name",
        [
            validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
            validators.DataRequired(),
            ValidateRegex(constants.NAME_VALIDATION),
        ],
    )
    role = SelectField(
        "Role", [validators.Length(min=3, max=32), validators.DataRequired()], default="member"
    )
    reason = TextAreaField("Reason", [validators.DataRequired()])
    expiration = StringField("Expiration", [ValidateDate()], id="add-form-expiration")


class GroupRemoveForm(Form):
    member = StringField(
        "Member",
        [
            validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
            validators.DataRequired(),
            ValidateRegex(constants.NAME_VALIDATION),
        ],
    )
    member_type = SelectField(
        "Member Type", [validators.DataRequired()], choices=[("user", "User"), ("group", "Group")]
    )


class GroupJoinForm(Form):
    member = SelectField(
        "Member",
        [
            validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
            validators.DataRequired(),
            ValidateRegex(r"(?:User|Group): {}".format(constants.NAME_VALIDATION)),
        ],
    )
    role = SelectField(
        "Role",
        [validators.Length(min=3, max=32), validators.DataRequired()],
        choices=[(role, role.title()) for role in GROUP_EDGE_ROLES],
        default="member",
    )
    reason = TextAreaField("Reason", [validators.DataRequired()])
    expiration = StringField("Expiration", [ValidateDate()], id="join-form-expiration")
    clickthru_agreement = BooleanField(
        "Acknowledge reading and accepting the terms of this group's membership",
        [validators.Optional()],
        default=False,
    )


class GroupEditMemberForm(Form):
    # Caller of the form will add choices based on role.
    role = SelectField("Role", [validators.Length(min=3, max=32), validators.DataRequired()])
    reason = TextAreaField("Reason", [validators.DataRequired()])
    expiration = StringField("Expiration", [ValidateDate()], id="edit-form-expiration")


class PermissionRequestForm(Form):
    # Caller will add <select> field choices.
    group_name = SelectField("Group", [validators.DataRequired()])
    permission = SelectField("Permission", [validators.DataRequired()])
    argument = StringField(
        "Argument",
        [
            validators.Length(min=0, max=constants.MAX_ARGUMENT_LENGTH),
            ValidateRegex(constants.ARGUMENT_VALIDATION),
        ],
    )
    reason = TextAreaField("Reason", [validators.DataRequired()])


class PermissionRequestsForm(Form):
    offset = IntegerField(default=0)
    limit = IntegerField(default=100, validators=[validators.NumberRange(min=100, max=9000)])
    # Caller of form will add choices for status.
    status = SelectField("New Status", [validators.Optional()], default="")
    direction = SelectField(
        "Direction",
        [validators.DataRequired()],
        choices=[("Waiting my approval", ""), ("Requested by me", "")],
        default="Waiting my approval",
    )


class PermissionRequestUpdateForm(Form):
    # Caller of form will add choices based on current status.
    status = SelectField("New Status", [validators.DataRequired()])
    reason = TextAreaField("Reason", [validators.DataRequired()])


class UserEnableForm(Form):
    preserve_membership = BooleanField(default=False)


class UsersPublicKeyForm(Form):
    offset = IntegerField(default=0)
    limit = IntegerField(default=100, validators=[validators.NumberRange(min=100, max=1000)])
    enabled = IntegerField(default=1, validators=[validators.NumberRange(min=0, max=1)])
    sort_by = StringField(
        validators=[validators.Optional(), validators.AnyOf(["age", "size", "type", "user"])]
    )
    fingerprint = StringField(
        label="fingerprint",
        validators=[validators.Optional(), validators.Regexp("^[A-Za-z0-9+/=]+$")],
        default=None,
    )


class UsersUserTokenForm(Form):
    offset = IntegerField(default=0)
    limit = IntegerField(default=100, validators=[validators.NumberRange(min=100, max=1000)])
    enabled = IntegerField(default=1, validators=[validators.NumberRange(min=0, max=1)])
    sort_by = StringField(
        validators=[validators.Optional(), validators.AnyOf(["age", "user", "name"])]
    )


class UserTokenForm(Form):
    name = StringField(
        "Token name",
        [
            validators.DataRequired(),
            validators.Length(min=1, max=16),
            ValidateRegex(constants.TOKEN_NAME_VALIDATION),
        ],
    )


class UserShellForm(Form):
    # Caller of form will add choices based on settings.
    shell = SelectField("Shell", [validators.DataRequired()])


class UserMetadataForm(Form):
    # Caller of form will add choices based on settings.
    value = SelectField("Value", [validators.DataRequired()])


class UserPasswordForm(Form):
    name = StringField(
        "Password name",
        [
            validators.DataRequired(),
            validators.Length(min=1, max=16),
            ValidateRegex(constants.TOKEN_NAME_VALIDATION),
        ],
    )
    password = PasswordField("Password", [validators.DataRequired()])


class ServiceAccountCreateForm(Form):
    # Allow either NAME or SERVICE_ACCOUNT validation since we allow people to specify just the
    # left-hand side of a service account name and add the domain automatically.
    name = StringField(
        "Name",
        [
            validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
            validators.DataRequired(),
            ValidateRegex(constants.NAME_VALIDATION + "|" + constants.SERVICE_ACCOUNT_VALIDATION),
        ],
    )
    description = TextAreaField("Description")
    machine_set = TextAreaField("Machine Set")


class ServiceAccountEditForm(Form):
    description = TextAreaField("Description")
    machine_set = TextAreaField("Machine Set")


class ServiceAccountEnableForm(Form):
    owner = SelectField(
        "Owner",
        [
            validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
            validators.DataRequired(),
            ValidateRegex(constants.NAME_VALIDATION),
        ],
    )


class ServiceAccountPermissionGrantForm(Form):
    # Caller of form will add choices.
    permission = SelectField("Permission", [validators.DataRequired()])
    argument = StringField(
        "Argument",
        [
            validators.Length(min=0, max=constants.MAX_NAME_LENGTH),
            ValidateRegex(constants.ARGUMENT_VALIDATION),
        ],
    )
