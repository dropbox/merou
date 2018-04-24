from base import BaseElement, BaseModal, BasePage
from exceptions import NoSuchElementException

from selenium.webdriver.support.select import Select


class GroupEditMemberPage(BasePage):
    def _get_edit_member_form(self):
        return self.find_element_by_class_name("edit-member-form")

    def set_expiration(self, expiration):
        form = self._get_edit_member_form()
        field = form.find_element_by_name("expiration")
        field.send_keys(expiration)

    def set_reason(self, reason):
        form = self._get_edit_member_form()
        field = form.find_element_by_name("reason")
        field.send_keys(reason)

    def submit(self):
        form = self._get_edit_member_form()
        form.submit()


class GroupsViewPage(BasePage):
    def find_group_row(self, name):
        for row in self.find_elements_by_class_name("group-row"):
            group_row = GroupRow(row)
            if group_row.name == name:
                return group_row

        raise NoSuchElementException("Can't find group with name {}".format(name))


class GroupViewPage(BasePage):
    def find_member_row(self, name):
        for row in self.find_elements_by_class_name("member-row"):
            member_row = MemberRow(row)
            if member_row.name == name:
                return member_row

        raise NoSuchElementException("Can't find member with name {}".format(name))

    def get_remove_user_modal(self):
        element = self.find_element_by_id("removeUserModal")
        return RemoveMemberModal(element)

    def get_audit_modal(self):
        element = self.find_element_by_id("auditModal")
        self.wait_until_visible(element)
        return AuditModal(element)

    def click_add_service_account_button(self):
        button = self.find_element_by_class_name("add-service-account")
        button.click()


class RoleUserViewPage(GroupViewPage):
    pass


class AuditModal(BaseModal):
    def find_member_row(self, name):
        for row in self.find_elements_by_class_name("audit-member-row"):
            member_row = AuditMemberRow(row)
            if member_row.name == name:
                return member_row

        raise NoSuchElementException("Can't find audit member with name {}".format(name))


class RemoveMemberModal(BaseModal):
    pass


class AuditMemberRow(BaseElement):
    @property
    def name(self):
        return self.find_element_by_class_name("audit-member-name").text

    def set_audit_status(self, status):
        status_cell = self.find_element_by_class_name("audit-member-status")
        status_select = status_cell.find_element_by_tag_name("select")
        Select(status_select).select_by_visible_text(status)


class GroupRow(BaseElement):
    @property
    def name(self):
        return self.find_element_by_class_name("group-name").text

    @property
    def href(self):
        name = self.find_element_by_class_name("group-name")
        link = name.find_element_by_tag_name("a")
        return link.get_attribute("href")


class MemberRow(BaseElement):
    def click_remove_button(self):
        button = self.find_element_by_class_name("remove-member")
        button.click()

    def click_edit_button(self):
        button = self.find_element_by_class_name("edit-member")
        button.click()

    @property
    def name(self):
        return self.find_element_by_class_name("member-name").text

    @property
    def href(self):
        name = self.find_element_by_class_name("member-name")
        link = name.find_element_by_tag_name("a")
        return link.get_attribute("href")

    @property
    def role(self):
        return self.find_element_by_class_name("member-role").text

    @property
    def expiration(self):
        return self.find_element_by_class_name("member-expiration").text
