from itests.pages.base import BasePage


class ErrorPage(BasePage):
    @property
    def content(self):
        # type: () -> str
        return self.find_element_by_id("content").text
