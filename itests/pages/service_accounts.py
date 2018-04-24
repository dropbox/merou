from base import BaseModal, BasePage

from selenium.webdriver.support.select import Select


class ServiceAccountViewPage(BasePage):
    def click_disable_button(self):
        button = self.find_element_by_class_name("disable-service-account")
        button.click()

    def click_enable_button(self):
        button = self.find_element_by_class_name("enable-service-account")
        button.click()

    def get_disable_modal(self):
        element = self.find_element_by_id("disableModal")
        self.wait_until_visible(element)
        return DisableServiceAccountModal(element)


class ServiceAccountCreatePage(BasePage):
    def _get_new_service_account_form(self):
        return self.find_element_by_class_name("new-service-account-form")

    def set_name(self, name):
        form = self._get_new_service_account_form()
        field = form.find_element_by_name("name")
        field.send_keys(name)

    def submit(self):
        form = self._get_new_service_account_form()
        form.submit()


class ServiceAccountEnablePage(BasePage):
    def _get_enable_service_account_form(self):
        return self.find_element_by_class_name("enable-service-account-form")

    def select_owner(self, owner):
        form = self._get_enable_service_account_form()
        owner_select = form.find_element_by_tag_name("select")
        Select(owner_select).select_by_visible_text(owner)

    def submit(self):
        form = self._get_enable_service_account_form()
        form.submit()


class DisableServiceAccountModal(BaseModal):
    pass
