from __future__ import annotations

from typing import TYPE_CHECKING

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select

from grouper.entities.group import GroupJoinPolicy
from itests.pages.base import BaseElement, BaseModal, BasePage
from itests.pages.permissions import PermissionGrantRow

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement
    from typing import List, Optional


class GroupCreatePage(BasePage):
    @property
    def form(self) -> WebElement:
        return self.find_element_by_id("create-form")

    def set_group_name(self, name: str) -> None:
        field = self.form.find_element_by_name("groupname")
        field.clear()
        field.send_keys(name)

    def submit(self) -> None:
        self.form.submit()


class GroupEditPage(BasePage):
    @property
    def form(self) -> WebElement:
        return self.find_element_by_id("edit-form")

    def set_name(self, name: str) -> None:
        field = self.form.find_element_by_name("groupname")
        field.clear()
        field.send_keys(name)

    def submit(self) -> None:
        self.form.submit()


class GroupEditMemberPage(BasePage):
    @property
    def form(self) -> WebElement:
        return self.find_element_by_class_name("edit-member-form")

    def get_role_options(self) -> List[str]:
        element = self.form.find_element_by_name("role")
        options = element.find_elements_by_tag_name("option")
        return [o.get_attribute("value") for o in options]

    def set_role(self, role: str) -> None:
        field = Select(self.form.find_element_by_name("role"))
        field.select_by_visible_text(role)

    def set_expiration(self, expiration: str) -> None:
        field = self.form.find_element_by_name("expiration")
        field.send_keys(expiration)

    def set_reason(self, reason: str) -> None:
        field = self.form.find_element_by_name("reason")
        field.send_keys(reason)

    def submit(self) -> None:
        self.form.submit()


class GroupsViewPage(BasePage):
    def find_group_row(self, name):
        # type: (str) -> GroupRow
        for row in self.find_elements_by_class_name("group-row"):
            group_row = GroupRow(row)
            if group_row.name == name:
                return group_row

        raise NoSuchElementException("Can't find group with name {}".format(name))

    def click_create_group_button(self):
        # type: () -> None
        button = self.find_element_by_id("create-group")
        button.click()

    def click_show_audited_button(self):
        # type: () -> None
        button = self.find_element_by_id("show-audited")
        button.click()

    def get_create_group_modal(self):
        # type: () -> CreateGroupModal
        element = self.find_element_by_id("createModal")
        self.wait_until_visible(element)
        return CreateGroupModal(element)


class GroupViewPage(BasePage):
    def find_member_row(self, name: str) -> MemberRow:
        for row in self.find_elements_by_class_name("member-row"):
            member_row = MemberRow(row)
            if member_row.name == name:
                return member_row

        raise NoSuchElementException("Can't find member with name {}".format(name))

    def find_permission_rows(
        self, name: str, argument: Optional[str] = None
    ) -> List[PermissionGrantRow]:
        elements = self.find_elements_by_class_name("permission-row")
        rows = [PermissionGrantRow(el) for el in elements]

        rows = [row for row in rows if row.name == name]

        if argument:
            rows = [row for row in rows if row.argument == argument]

        return rows

    def get_remove_user_modal(self) -> RemoveMemberModal:
        element = self.find_element_by_id("removeUserModal")
        return RemoveMemberModal(element)

    def get_audit_modal(self) -> AuditModal:
        element = self.find_element_by_id("auditModal")
        self.wait_until_visible(element)
        return AuditModal(element)

    def click_edit_button(self) -> None:
        button = self.find_element_by_id("edit-group")
        button.click()

    def click_add_permission_button(self) -> None:
        button = self.find_element_by_id("add-permission")
        button.click()

    def click_add_service_account_button(self) -> None:
        button = self.find_element_by_id("add-service-account")
        button.click()

    def click_disable_button(self) -> None:
        button = self.find_element_by_id("disable-group")
        button.click()

    def click_leave_button(self) -> None:
        button = self.find_element_by_id("leave-group")
        button.click()

    def click_request_permission_button(self) -> None:
        button = self.find_element_by_id("request-permission")
        button.click()

    def get_disable_modal(self) -> DisableGroupModal:
        element = self.find_element_by_id("disableModal")
        self.wait_until_visible(element)
        return DisableGroupModal(element)

    def wait_until_audit_modal_clears(self) -> None:
        audit_modal = self.find_element_by_id("auditModal")
        self.wait_until_invisible(audit_modal)


class GroupJoinPage(BasePage):
    @property
    def form(self):
        # type: () -> WebElement
        return self.find_element_by_class_name("join-group-form")

    def get_alerts(self):
        # type: () -> List[WebElement]
        return self.find_elements_by_class_name("alert")

    def get_clickthru_modal(self):
        # type: () -> GroupJoinClickthruModal
        element = self.find_element_by_id("clickthruModal")
        self.wait_until_visible(element)
        return GroupJoinClickthruModal(element)

    def get_member_options(self):
        # type: () -> List[WebElement]
        element = self.find_element_by_name("member")
        return element.find_elements_by_tag_name("option")

    def set_member(self, member):
        # type: (str) -> None
        member_select = self.form.find_element_by_id("member_chosen")
        member_select.click()
        member_search = member_select.find_element_by_tag_name("input")
        member_search.send_keys(member, Keys.ENTER)

    def set_role(self, role):
        # type: (str) -> None
        field = Select(self.form.find_element_by_name("role"))
        field.select_by_visible_text(role)

    def set_expiration(self, expiration):
        # type: (str) -> None
        field = self.form.find_element_by_name("expiration")
        field.send_keys(expiration)

        # This will have popped up a date picker.  We need to click outside of the picker to
        # dismiss it so that it doesn't hide the form submit button.
        self.form.find_element_by_id("reason").click()

    def set_reason(self, reason):
        # type: (str) -> None
        field = self.form.find_element_by_id("reason")
        field.send_keys(reason)

    def submit(self):
        # type: () -> None
        self.form.find_element_by_id("join-btn").click()


class GroupLeavePage(BasePage):
    @property
    def form(self) -> WebElement:
        return self.find_element_by_id("leave-group-form")

    def submit(self) -> None:
        self.form.submit()


class PermissionGrantPage(BasePage):
    @property
    def form(self) -> WebElement:
        return self.find_element_by_id("grant-form")

    def set_permission(self, permission: str) -> None:
        permission_select = self.form.find_element_by_id("permission_chosen")
        permission_select.click()
        permission_search = permission_select.find_element_by_tag_name("input")
        permission_search.send_keys(permission, Keys.ENTER)

    def set_argument(self, argument: str) -> None:
        field = self.form.find_element_by_name("argument")
        field.send_keys(argument)

    def submit(self) -> None:
        self.form.submit()


class GroupRequestsPage(BasePage):
    def find_request_row(self, requested):
        # type: (str) -> GroupRequestRow
        for row in self.find_elements_by_class_name("group-request-row"):
            request_row = GroupRequestRow(row)
            if request_row.requested == requested:
                return request_row

        raise NoSuchElementException(
            "Can't find request with requested member {}".format(requested)
        )


class AuditModal(BaseModal):
    def click_close_button(self) -> None:
        button = self.find_element_by_id("audit-close")
        button.click()

    def find_member_row(self, name: str) -> AuditMemberRow:
        for row in self.find_elements_by_class_name("audit-member-row"):
            member_row = AuditMemberRow(row)
            if member_row.name == name:
                return member_row
        raise NoSuchElementException(f"Can't find audit member with name {name}")


class CreateGroupModal(BaseModal):
    @property
    def form(self):
        # type: () -> WebElement
        return self.find_element_by_tag_name("form")

    def click_require_clickthru_checkbox(self):
        # type: () -> None
        self.form.find_element_by_name("require_clickthru_tojoin").click()

    def set_group_name(self, name):
        # type: (str) -> None
        field = self.form.find_element_by_name("groupname")
        field.send_keys(name)

    def set_description(self, description):
        # type: (str) -> None
        field = self.form.find_element_by_name("description")
        field.send_keys(description)

    def set_join_policy(self, join_policy):
        # type: (GroupJoinPolicy) -> None
        field = Select(self.form.find_element_by_name("canjoin"))
        field.select_by_value(join_policy.value)


class DisableGroupModal(BaseModal):
    pass


class GroupJoinClickthruModal(BaseModal):
    def confirm(self):
        # type: () -> None
        self.find_element_by_id("agree-clickthru-btn").click()


class RemoveMemberModal(BaseModal):
    pass


class AuditMemberRow(BaseElement):
    @property
    def name(self):
        # type: () -> str
        return self.find_element_by_class_name("audit-member-name").text

    def set_audit_status(self, status):
        # type: (str) -> None
        status_cell = self.find_element_by_class_name("audit-member-status")
        status_select = status_cell.find_element_by_tag_name("select")
        Select(status_select).select_by_visible_text(status)


class GroupRow(BaseElement):
    @property
    def name(self):
        # type: () -> str
        return self.find_element_by_class_name("group-name").text

    @property
    def href(self):
        # type: () -> str
        name = self.find_element_by_class_name("group-name")
        link = name.find_element_by_tag_name("a")
        return link.get_attribute("href")

    @property
    def description(self):
        # type: () -> str
        return self.find_element_by_class_name("group-description").text

    @property
    def can_join(self):
        # type: () -> str
        return self.find_element_by_class_name("group-can-join").text

    @property
    def audited_reason(self):
        # type: () -> str
        return self.find_element_by_class_name("group-why-audited").text


class MemberRow(BaseElement):
    def click_remove_button(self):
        # type: () -> None
        button = self.find_element_by_class_name("remove-member")
        button.click()

    def click_edit_button(self):
        # type: () -> None
        button = self.find_element_by_class_name("edit-member")
        button.click()

    @property
    def name(self):
        # type: () -> str
        return self.find_element_by_class_name("member-name").text

    @property
    def href(self):
        # type: () -> str
        name = self.find_element_by_class_name("member-name")
        link = name.find_element_by_tag_name("a")
        return link.get_attribute("href")

    @property
    def role(self):
        # type: () -> str
        return self.find_element_by_class_name("member-role").text

    @property
    def expiration(self):
        # type: () -> str
        return self.find_element_by_class_name("member-expiration").text


class GroupRequestRow(BaseElement):
    @property
    def requested(self):
        # type: () -> str
        return self.find_element_by_class_name("request-requested").text

    @property
    def requester(self):
        # type: () -> str
        return self.find_element_by_class_name("request-requester").text

    @property
    def status(self):
        # type: () -> str
        return self.find_element_by_class_name("request-status").text

    @property
    def requested_at(self):
        # type: () -> str
        return self.find_element_by_class_name("request-requested-at").text

    @property
    def expiration(self):
        # type: () -> str
        return self.find_element_by_class_name("request-expiration").text

    @property
    def role(self):
        # type: () -> str
        return self.find_element_by_class_name("request-role").text

    @property
    def reason(self):
        # type: () -> str
        return self.find_element_by_class_name("request-reason").text
