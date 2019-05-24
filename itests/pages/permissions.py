from typing import TYPE_CHECKING

from selenium.common.exceptions import NoSuchElementException

from itests.pages.base import BaseElement, BasePage

if TYPE_CHECKING:
    from typing import List


class PermissionsPage(BasePage):
    @property
    def has_create_permission_button(self):
        # type: () -> bool
        try:
            self.find_element_by_id("create-permission")
            return True
        except NoSuchElementException:
            return False

    @property
    def permission_rows(self):
        # type: () -> List[PermissionRow]
        all_permission_rows = self.find_elements_by_class_name("permission-row")
        return [PermissionRow(row) for row in all_permission_rows]

    @property
    def limit_label(self):
        # type: () -> str
        return self.find_element_by_id("dropdown-limit").text.strip()

    def click_create_permission_button(self):
        # type: () -> None
        button = self.find_element_by_id("create-permission")
        button.click()

    def click_show_all_button(self):
        # type: () -> None
        button = self.find_element_by_id("show-all")
        button.click()

    def click_show_audited_button(self):
        # type: () -> None
        button = self.find_element_by_id("show-audited")
        button.click()

    def click_sort_by_date(self):
        # type: () -> None
        heading = self.find_element_by_class_name("col-date")
        link = heading.find_element_by_tag_name("a")
        self.root.get(link.get_attribute("href"))


class PermissionRow(BaseElement):
    @property
    def name(self):
        # type: () -> str
        return self.find_element_by_class_name("permission-name").text

    @property
    def description(self):
        # type: () -> str
        return self.find_element_by_class_name("permission-description").text

    @property
    def created_on(self):
        # type: () -> str
        return self.find_element_by_class_name("permission-created-on").text


class PermissionGrantRow(BaseElement):
    @property
    def name(self):
        return self.find_element_by_class_name("permission-name").text

    @property
    def href(self):
        name = self.find_element_by_class_name("permission-name")
        link = name.find_element_by_tag_name("a")
        return link.get_attribute("href")

    @property
    def argument(self):
        return self.find_element_by_class_name("permission-argument").text

    @property
    def source(self):
        return self.find_element_by_class_name("permission-source").text

    @property
    def granted_on(self):
        return self.find_element_by_class_name("permission-granted-on").text
