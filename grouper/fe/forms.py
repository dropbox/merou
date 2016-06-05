from datetime import datetime, timedelta
import re

import sshpubkey
from wtforms import (
        BooleanField,
        HiddenField,
        IntegerField,
        SelectField,
        StringField,
        TextAreaField,
        validators,
        )
from wtforms.validators import ValidationError
from wtforms_tornado import Form

from .. import constants
from .. import model_soup


class ValidateRegex(object):
    def __init__(self, regex):
        # We assume any regex passed to us does not have line anchors.
        self.regex = r'^' + regex + r'$'
        self._re = re.compile(self.regex)

    def __call__(self, form, field):
        if not self._re.match(field.data):
            raise ValidationError("Field must match '{}'".format(self.regex))


class ValidateDate(object):
    def __call__(self, form, field):
        try:
            if field.data:
                datetime.strptime(field.data, "%m/%d/%Y")
        except ValueError:
            raise ValidationError(
                "{} does not match format 'MM/DD/YYYY'".format(field.data))


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
            super(DaysTimeDeltaField, self).process_formdata(valuelist)
            self.data = timedelta(days=self.data)
        else:
            self.data = None


class ValidatePublicKey(object):
    # TODO: Add ability to specify things like bit depth, key type, etc, as requirements
    # for what kind of keys are allowed.
    def __call__(self, form, field):
        try:
            sshpubkey.PublicKey.from_str(field.data)
        except sshpubkey.exc.PublicKeyParseError:
            raise ValidationError("Public key appears to be invalid.")


class PublicKeyForm(Form):
    public_key = TextAreaField("Public Key", [
        validators.DataRequired(),
        ValidatePublicKey(),
    ])


class PermissionGrantForm(Form):
    permission = SelectField("Permission", [
        validators.DataRequired(),
    ], choices=[["", "(select one)"]], default="")
    argument = StringField("Argument", [
        validators.Length(min=0, max=constants.MAX_NAME_LENGTH),
        ValidateRegex(constants.ARGUMENT_VALIDATION),
    ])


class PermissionCreateForm(Form):
    name = StringField("Name", [
        validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
        validators.DataRequired(),
        ValidateRegex(constants.PERMISSION_VALIDATION),
    ])
    description = TextAreaField("Description")


class GroupCreateForm(Form):
    creatorrole = SelectField("Creator role", choices=[
            ("owner", "Owner"), ("np-owner", "No-Permissions Owner"),
            ], default="owner")
    groupname = StringField("Name", [
        validators.Length(min=3, max=32),
        validators.DataRequired(),
        ValidateRegex(constants.NAME_VALIDATION),
    ])
    description = TextAreaField("Description")
    canjoin = SelectField("Who Can Join?", choices=[
        ("canjoin", "Anyone"), ("canask", "Must Ask"),
        ("nobody", "Nobody"),
    ], default="canask")
    auto_expire = DaysTimeDeltaField("Default Expiration (Days)")


class GroupEditForm(Form):
    groupname = StringField("Name", [
        validators.Length(min=3, max=32),
        validators.DataRequired(),
        ValidateRegex(constants.NAME_VALIDATION),
    ])
    description = TextAreaField("Description")
    canjoin = SelectField("Who Can Join?", choices=[
        ("canjoin", "Anyone"), ("canask", "Must Ask"),
        ("nobody", "Nobody"),
    ], default="canask")
    auto_expire = DaysTimeDeltaField("Default Expiration (Days)")


class AuditCreateForm(Form):
    ends_at = StringField("Ends At", [
        ValidateDate(),
        validators.DataRequired(),
    ], id="audit-form-ends-at")


class GroupRequestModifyForm(Form):
    status = SelectField("New Status", [
        validators.DataRequired(),
    ])
    reason = TextAreaField("Reason", [
        validators.DataRequired(),
    ])
    redirect_aggregate = HiddenField()


class GroupAddForm(Form):
    member = SelectField("Name", [
        validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
        validators.DataRequired(),
        ValidateRegex(constants.NAME_VALIDATION),
    ])
    role = SelectField("Role", [
        validators.Length(min=3, max=32),
        validators.DataRequired(),
    ], default="member")
    reason = TextAreaField("Reason", [
        validators.DataRequired(),
    ])
    expiration = StringField("Expiration", [
        ValidateDate(),
    ], id="add-form-expiration")


class GroupRemoveForm(Form):
    member = StringField("Member", [
        validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
        validators.DataRequired(),
        ValidateRegex(constants.NAME_VALIDATION),
    ])
    member_type = SelectField("Member Type", [
        validators.DataRequired(),
    ], choices=[
        ("user", "User"), ("group", "Group"),
    ])


class GroupJoinForm(Form):
    member = SelectField("Member", [
        validators.Length(min=3, max=constants.MAX_NAME_LENGTH),
        validators.DataRequired(),
        ValidateRegex(r"(?:User|Member|Group): {}".format(constants.NAME_VALIDATION)),
    ])
    role = SelectField("Role", [
        validators.Length(min=3, max=32),
        validators.DataRequired(),
    ], choices=[
        (role, role.title())
        for role in model_soup.GROUP_EDGE_ROLES
    ], default="member")
    reason = TextAreaField("Reason", [
        validators.DataRequired(),
    ])
    expiration = StringField("Expiration", [
        ValidateDate(),
    ], id="join-form-expiration")


class GroupEditMemberForm(Form):
    role = SelectField("Role", [
        validators.Length(min=3, max=32),
        validators.DataRequired(),
    ])
    reason = TextAreaField("Reason", [
        validators.DataRequired(),
    ])
    expiration = StringField("Expiration", [
        ValidateDate(),
    ], id="edit-form-expiration")


class GroupPermissionRequestDropdownForm(Form):
    """permission request form using a dropdown field for the argument."""
    permission_name = SelectField("Permission", [
        validators.DataRequired(),
    ])
    argument = SelectField("Argument", [
        validators.DataRequired(),
    ])
    reason = TextAreaField("Reason", [
        validators.DataRequired(),
    ])
    argument_type = HiddenField(default="dropdown")


class GroupPermissionRequestTextForm(Form):
    """permission request form using a text field for the argument."""
    permission_name = SelectField("Permission", [
        validators.DataRequired(),
    ])
    argument = StringField("Argument", [
        validators.DataRequired(),
    ])
    reason = TextAreaField("Reason", [
        validators.DataRequired(),
    ])
    argument_type = HiddenField(default="text")


class PermissionRequestsForm(Form):
    offset = IntegerField(default=0)
    limit = IntegerField(default=100, validators=[validators.NumberRange(min=100, max=9000)])
    status = SelectField("New Status", [
        validators.Optional(),
    ], default='')


class PermissionRequestUpdateForm(Form):
    status = SelectField("New Status", [
        validators.DataRequired(),
    ])
    reason = TextAreaField("Reason", [
        validators.DataRequired(),
    ])


class UserEnableForm(Form):
    preserve_membership = BooleanField(default=False)


class UsersPublicKeyForm(Form):
    offset = IntegerField(default=0)
    limit = IntegerField(default=100, validators=[validators.NumberRange(min=100, max=1000)])
    enabled = IntegerField(default=1, validators=[validators.NumberRange(min=0, max=1)])
    sort_by = StringField(validators=[
            validators.Optional(),
            validators.AnyOf(["age", "size", "type", "user"]),
            ])
    fingerprint = StringField(label="fingerprint", validators=[
            validators.Optional(),
            validators.Regexp("^[\w:]+$"),
            ],
            default=None)


class UsersUserTokenForm(Form):
    offset = IntegerField(default=0)
    limit = IntegerField(default=100, validators=[validators.NumberRange(min=100, max=1000)])
    enabled = IntegerField(default=1, validators=[validators.NumberRange(min=0, max=1)])
    sort_by = StringField(validators=[
            validators.Optional(),
            validators.AnyOf(["age", "user", "name"]),
            ])


class UserTokenForm(Form):
    name = StringField("Token name", [
        validators.DataRequired(),
    ])


class UserShellForm(Form):
    shell = SelectField("Shell", [
        validators.DataRequired(),
    ])
