from typing import TYPE_CHECKING

from selenium.webdriver.support.select import Select

from itests.pages.base import BaseElement, BaseModal, BasePage

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement
    from typing import List


class ServiceAccountViewPage(BasePage):
    @property
    def permission_rows(self):
        # type: () -> List[ServiceAccountPermissionRow]
        all_permission_rows = self.find_elements_by_class_name("permission-row")
        return [ServiceAccountPermissionRow(row) for row in all_permission_rows]

    def click_add_permission_button(self):
        # type: () -> None
        button = self.find_element_by_id("add-permission")
        button.click()

    def click_disable_button(self):
        # type: () -> None
        button = self.find_element_by_class_name("disable-service-account")
        button.click()

    def click_enable_button(self):
        # type: () -> None
        button = self.find_element_by_class_name("enable-service-account")
        button.click()

    def get_disable_modal(self):
        # type: () -> DisableServiceAccountModal
        element = self.find_element_by_id("disableModal")
        self.wait_until_visible(element)
        return DisableServiceAccountModal(element)

    def get_revoke_permission_modal(self):
        # type: () -> RevokeServiceAccountPermissionModal
        element = self.find_element_by_id("revokeModal")
        self.wait_until_visible(element)
        return RevokeServiceAccountPermissionModal(element)


class ServiceAccountCreatePage(BasePage):
    def _get_new_service_account_form(self):
        # type: () -> WebElement
        return self.find_element_by_class_name("new-service-account-form")

    def set_name(self, name):
        # type: (str) -> None
        form = self._get_new_service_account_form()
        field = form.find_element_by_name("name")
        field.send_keys(name)

    def submit(self):
        # type: () -> None
        form = self._get_new_service_account_form()
        form.submit()


class ServiceAccountEnablePage(BasePage):
    def _get_enable_service_account_form(self):
        # type: () -> WebElement
        return self.find_element_by_class_name("enable-service-account-form")

    def select_owner(self, owner):
        # type: (str) -> None
        form = self._get_enable_service_account_form()
        owner_select = form.find_element_by_tag_name("select")
        Select(owner_select).select_by_visible_text(owner)

    def submit(self):
        # type: () -> None
        form = self._get_enable_service_account_form()
        form.submit()


class ServiceAccountGrantPermissionPage(BasePage):
    def _get_grant_permission_form(self):
        # type: () -> WebElement
        return self.find_element_by_id("grant-permission-form")

    def select_permission(self, permission):
        # type: (str) -> None
        form = self._get_grant_permission_form()
        permission_select = form.find_element_by_name("permission")
        Select(permission_select).select_by_visible_text(permission)

    def set_argument(self, argument):
        # type: (str) -> None
        form = self._get_grant_permission_form()
        field = form.find_element_by_name("argument")
        field.send_keys(argument)

    def submit(self):
        # type: () -> None
        form = self._get_grant_permission_form()
        form.submit()


class DisableServiceAccountModal(BaseModal):
    pass


class RevokeServiceAccountPermissionModal(BaseModal):
    pass


class ServiceAccountPermissionRow(BaseElement):
    @property
    def permission(self):
        # type: () -> str
        return self.find_element_by_class_name("permission-name").text

    @property
    def argument(self):
        # type: () -> str
        return self.find_element_by_class_name("permission-argument").text

    def click_revoke_button(self):
        # type: () -> None
        button = self.find_element_by_class_name("permission-revoke")
        button.click()
