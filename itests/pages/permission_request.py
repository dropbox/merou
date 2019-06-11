from typing import TYPE_CHECKING

from selenium.webdriver.support.ui import Select

from itests.pages.base import BasePage

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement
    from typing import List


class PermissionRequestPage(BasePage):
    @property
    def permission_request_form(self):
        # type: () -> WebElement
        return self.find_element_by_id("permission-request")

    def get_option_values(self, name):
        # type: (str) -> List[str]
        select = Select(self.permission_request_form.find_element_by_name(name))
        return [option.get_attribute("value") for option in select.options]

    def set_select_value(self, name, value):
        # type: (str, str) -> None
        select = Select(self.permission_request_form.find_element_by_name(name))
        select.select_by_value(value)

    def fill_field(self, name, value):
        # type: (str, str) -> None
        self.permission_request_form.find_element_by_name(name).send_keys(value)

    def submit_request(self):
        # type: () -> None
        button = self.permission_request_form.find_element_by_tag_name("button")
        button.click()
