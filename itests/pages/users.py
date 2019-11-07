from selenium.common.exceptions import NoSuchElementException

from itests.pages.base import BaseElement, BaseModal, BasePage
from itests.pages.permissions import PermissionGrantRow


class PublicKeysPage(BasePage):
    def find_public_key_row(self, fingerprint_sha256):
        for row in self.find_elements_by_class_name("public-key-row"):
            member_row = PublicKeyRow(row)
            if member_row.fingerprint_sha256 == fingerprint_sha256:
                return member_row

        raise NoSuchElementException(
            "Can't find public key with fingerprint {}".format(fingerprint_sha256)
        )


class UsersViewPage(BasePage):
    def click_show_disabled_users_button(self):
        button = self.find_element_by_class_name("show-disabled-users")
        button.click()

    def click_show_service_accounts_button(self):
        button = self.find_element_by_class_name("show-service-accounts")
        button.click()

    def find_user_row(self, name):
        for row in self.find_elements_by_class_name("user-row"):
            user_row = UserRow(row)
            if user_row.name == name:
                return user_row

        raise NoSuchElementException("Can't find user with name {}".format(name))


class UserViewPage(BasePage):
    def click_disable_button(self):
        button = self.find_element_by_class_name("disable-user")
        button.click()

    def get_disable_user_modal(self):
        element = self.find_element_by_id("disableModal")
        return DisableUserModal(element)

    def find_permission_rows(self, name, argument=None):
        elements = self.find_elements_by_class_name("permission-row")
        rows = [PermissionGrantRow(el) for el in elements]

        rows = [row for row in rows if row.name == name]

        if argument:
            rows = [row for row in rows if row.argument == argument]

        return rows


class DisableUserModal(BaseModal):
    pass


class PublicKeyRow(BaseElement):
    @property
    def user(self):
        return self.find_element_by_class_name("public-key-user").text

    @property
    def key_type(self):
        return self.find_element_by_class_name("public-key-type").text

    @property
    def key_size(self):
        return self.find_element_by_class_name("public-key-size").text

    @property
    def fingerprint_sha256(self):
        return self.find_element_by_class_name("public-key-fingerprint-sha256").text


class UserRow(BaseElement):
    @property
    def name(self):
        return self.find_element_by_class_name("user-name").text

    def click(self):
        link = self.find_element_by_class_name("account-link")
        link.click()
