from base import BaseElement, BasePage


class PermissionRequestsPage(BasePage):
    @property
    def request_rows(self):
        all_request_rows = self.find_elements_by_class_name("request-row")
        return [RequestViewRow(row) for row in all_request_rows]

    @property
    def status_change_rows(self):
        all_sc_rows = self.find_elements_by_class_name("request-status-change-row")
        return [StatusChangeRow(row) for row in all_sc_rows]

    @property
    def no_requests_row(self):
        return self.find_element_by_class_name("request-dne")


class RequestViewRow(BaseElement):
    @property
    def modify_link(self):
        modify = self.find_element_by_class_name("request-modify")
        link = modify.find_element_by_tag_name("a")
        return link.get_attribute("href")

    @property
    def requested(self):
        return self.find_element_by_class_name("request-requested").text

    @property
    def approvers(self):
        return self.find_element_by_class_name("request-approvers").text

    @property
    def status(self):
        return self.find_element_by_class_name("request-status").text

    @property
    def requested_at(self):
        return self.find_element_by_class_name("request-requested-at").text


class StatusChangeRow(BaseElement):
    @property
    def group(self):
        return self.find_element_by_class_name("request-group").text

    @property
    def who(self):
        return self.find_element_by_class_name("request-who").text

    @property
    def reason(self):
        return self.find_element_by_class_name("request-reason").text
