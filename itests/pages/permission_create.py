from typing import TYPE_CHECKING

from itests.pages.base import BasePage

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement
    from typing import List


class PermissionCreatePage(BasePage):
    @property
    def allowed_patterns(self):
        # type: () -> List[str]
        patterns = self.find_element_by_id("allowed-patterns")
        return [e.text for e in patterns.find_elements_by_tag_name("strong")]

    @property
    def form(self):
        # type: () -> WebElement
        return self.find_element_by_id("permission-create-form")

    def set_description(self, description):
        # type: (str) -> None
        field = self.form.find_element_by_name("description")
        field.send_keys(description)

    def set_name(self, name):
        # type: (str) -> None
        field = self.form.find_element_by_name("name")
        field.send_keys(name)
