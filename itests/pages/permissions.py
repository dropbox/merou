from base import BaseElement


class PermissionRow(BaseElement):
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
