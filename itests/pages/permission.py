from itests.pages.base import BaseElement, BasePage


class PermissionPage(BasePage):
    @property
    def button_to_request_this_permission(self):
        buttons = self.find_elements_by_class_name("btn")
        return next(b for b in buttons if b.text == u"Request this permission")
