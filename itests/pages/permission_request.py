from __future__ import annotations

from typing import TYPE_CHECKING

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

from itests.pages.base import BasePage

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement
    from typing import List


class PermissionRequestPage(BasePage):
    @property
    def form(self) -> WebElement:
        return self.find_element_by_id("permission-request")

    def get_group_values(self) -> List[str]:
        field = Select(self.form.find_element_by_name("group_name"))
        return [option.get_attribute("value") for option in field.options]

    def get_permission_values(self) -> List[str]:
        field = Select(self.form.find_element_by_name("permission"))
        return [option.get_attribute("value") for option in field.options]

    def set_group(self, group: str) -> None:
        field = Select(self.form.find_element_by_name("group_name"))
        field.select_by_value(group)

    def set_permission(self, permission: str) -> None:
        permission_select = self.form.find_element_by_id("permission_chosen")
        permission_select.click()
        permission_search = permission_select.find_element_by_tag_name("input")
        permission_search.send_keys(permission, Keys.ENTER)

    def set_argument_dropdown(self, argument: str) -> None:
        field = Select(self.form.find_element_by_name("argument"))
        field.select_by_value(argument)

    def set_argument_freeform(self, argument: str) -> None:
        field = self.form.find_element_by_name("argument")
        field.send_keys(argument)

    def set_reason(self, reason: str) -> None:
        field = self.form.find_element_by_name("reason")
        field.send_keys(reason)

    def submit(self) -> None:
        self.form.submit()
