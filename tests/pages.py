from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class NoSuchElementException(Exception):
    pass


class BaseFinder(object):
    def __init__(self, root):
        self.root = root

    def find_element_by_class_name(self, name):
        return self.root.find_element_by_class_name(name)

    def find_elements_by_class_name(self, name):
        return self.root.find_elements_by_class_name(name)

    def find_element_by_id(self, id_):
        return self.root.find_element_by_id(id_)

    def find_element_by_tag_name(self, name):
        return self.root.find_element_by_tag_name(name)


class BasePage(BaseFinder):
    @property
    def current_url(self):
        return self.root.current_url

    def has_text(self, text):
        return text in self.root.page_source

    def wait_until_visible(self, element):
        WebDriverWait(self.root, 10).until(EC.visibility_of(element))


class BaseElement(BaseFinder):
    @property
    def text(self):
        return self.root.text


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


class RoleUserViewPage(GroupViewPage):
    pass


class UserViewPage(BasePage):
    def click_disable_button(self):
        button = self.find_element_by_class_name("disable-user")
        button.click()

    def get_disable_user_modal(self):
        element = self.find_element_by_id("disableModal")
        return DisableUserModal(element)


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


class AuditsCreatePage(BasePage):
    def _get_new_audit_form(self):
        return self.find_element_by_class_name("new-audit-form")

    def set_end_date(self, end_date):
        form = self._get_new_audit_form()
        field = form.find_element_by_name("ends_at")
        field.send_keys(end_date)

    def submit(self):
        form = self._get_new_audit_form()
        form.submit()


class BaseModal(BaseElement):
    def confirm(self):
        form = self.find_element_by_tag_name("form")
        form.submit()


class RemoveMemberModal(BaseModal):
    pass


class DisableUserModal(BaseModal):
    pass


class AuditModal(BaseModal):
    def find_member_row(self, name):
        for row in self.find_elements_by_class_name("audit-member-row"):
            member_row = AuditMemberRow(row)
            if member_row.name == name:
                return member_row

        raise NoSuchElementException("Can't find audit member with name {}".format(name))


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


class GroupRow(BaseElement):
    @property
    def name(self):
        return self.find_element_by_class_name("group-name").text

    @property
    def href(self):
        name = self.find_element_by_class_name("group-name")
        link = name.find_element_by_tag_name("a")
        return link.get_attribute("href")


class AuditMemberRow(BaseElement):
    @property
    def name(self):
        return self.find_element_by_class_name("audit-member-name").text

    def set_audit_status(self, status):
        status_cell = self.find_element_by_class_name("audit-member-status")
        status_select = status_cell.find_element_by_tag_name("select")
        Select(status_select).select_by_visible_text(status)
