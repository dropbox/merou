from typing import TYPE_CHECKING

from itests.pages.base import BasePage
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

if TYPE_CHECKING:
    from typing import List


class PermissionRequestPage(BasePage):
    def get_option_values(self, id):
        # type: (str) -> List[str]
        select = Select(self.find_element_by_id(id))
        return [option.get_attribute("value") for option in select.options]

    def set_select_value(self, id, value):
        # type: (str, str) -> None
        select = Select(self.find_element_by_id(id))
        select.select_by_value(value)

    def fill_field(self, id, value):
        self.find_element_by_id(id).send_keys(value)

    def submit_request(self):
        self.find_element_by_id("argument").send_keys(Keys.ENTER)
