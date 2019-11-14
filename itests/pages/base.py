from __future__ import annotations

from typing import TYPE_CHECKING

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

if TYPE_CHECKING:
    from selenium.webdriver import Chrome
    from selenium.webdriver.remote.webelement import WebElement


class BaseFinder:
    def __init__(self, root):
        # type: (Chrome) -> None
        self.root = root

    def find_element_by_class_name(self, name):
        # type: (str) -> WebElement
        return self.root.find_element_by_class_name(name)

    def find_elements_by_class_name(self, name):
        # type: (str) -> WebElement
        return self.root.find_elements_by_class_name(name)

    def find_element_by_id(self, id_):
        # type: (str) -> WebElement
        return self.root.find_element_by_id(id_)

    def find_element_by_link_text(self, link_text):
        # type: (str) -> WebElement
        return self.root.find_element_by_link_text(link_text)

    def find_element_by_name(self, name):
        # type: (str) -> WebElement
        return self.root.find_element_by_name(name)

    def find_element_by_tag_name(self, name):
        # type: (str) -> WebElement
        return self.root.find_element_by_tag_name(name)


class BasePage(BaseFinder):
    @property
    def current_url(self):
        return self.root.current_url

    @property
    def heading(self):
        # type: () -> str
        return self.find_element_by_id("heading").text

    @property
    def subheading(self):
        # type: () -> str
        return self.find_element_by_id("subheading").text

    @property
    def search_input(self):
        # type: () -> WebElement
        return self.find_element_by_id("query")

    def click_search_button(self):
        # type: () -> None
        button = self.find_element_by_id("search")
        button.click()

    def has_alert(self, text):
        # type: (str) -> bool
        alerts = self.find_elements_by_class_name("alert")
        for alert in alerts:
            if text in alert.text:
                return True
        return False

    def has_text(self, text):
        return text in self.root.page_source

    def wait_until_invisible(self, element: WebElement) -> None:
        WebDriverWait(self.root, 10).until(EC.invisibility_of_element(element))

    def wait_until_visible(self, element):
        WebDriverWait(self.root, 10).until(EC.visibility_of(element))


class BaseElement(BaseFinder):
    @property
    def text(self):
        return self.root.text


class BaseModal(BaseElement):
    def confirm(self):
        form = self.find_element_by_tag_name("form")
        form.submit()
