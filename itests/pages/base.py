from typing import TYPE_CHECKING

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement


class BaseFinder(object):
    def __init__(self, root):
        self.root = root

    def find_element_by_class_name(self, name):
        return self.root.find_element_by_class_name(name)

    def find_elements_by_class_name(self, name):
        return self.root.find_elements_by_class_name(name)

    def find_element_by_id(self, id_):
        return self.root.find_element_by_id(id_)

    def find_element_by_link_text(self, link_text):
        return self.root.find_element_by_link_text(link_text)

    def find_element_by_tag_name(self, name):
        return self.root.find_element_by_tag_name(name)

    def find_element_by_xpath(self, path):
        return self.root.find_element_by_xpath(path)


class BasePage(BaseFinder):
    @property
    def current_url(self):
        return self.root.current_url

    @property
    def heading(self):
        # type: () -> str
        return self.find_element_by_xpath("//div[@class='header']/h2[1]").text

    @property
    def subheading(self):
        # type: () -> str
        return self.find_element_by_xpath("//div[@class='header']/h3[1]/small[1]").text

    @property
    def search_input(self):
        # type: () -> WebElement
        return self.find_element_by_xpath("//div[contains(@class, 'search-input')]/input[1]")

    def click_search_button(self):
        # type: () -> None
        button = self.find_element_by_xpath("//div[contains(@class, 'search-input')]//button[1]")
        button.click()

    def has_text(self, text):
        return text in self.root.page_source

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
