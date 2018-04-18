from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


class BaseFinder(object):
    def __init__(self, root):
        self.root = root

    def find_element_by_class_name(self, name):
        return self.root.find_element_by_class_name(name)

    def find_elements_by_class_name(self, name):
        return self.root.find_elements_by_class_name(name)

    def find_element_by_id(self, id_):
        return self.root.find_element_by_id(id_)

    def find_element_by_tag_name(self, name):
        return self.root.find_element_by_tag_name(name)

    def find_element_by_link_text(self, link_text):
        return self.root.find_element_by_link_text(link_text)


class BasePage(BaseFinder):
    @property
    def current_url(self):
        return self.root.current_url

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
