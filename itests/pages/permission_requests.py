from __future__ import annotations

from typing import TYPE_CHECKING

from selenium.webdriver.support.select import Select

from itests.pages.base import BaseElement, BasePage

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement
    from typing import List


class PermissionRequestsPage(BasePage):
    @property
    def request_rows(self) -> List[RequestViewRow]:
        all_request_rows = self.find_elements_by_class_name("request-row")
        return [RequestViewRow(row) for row in all_request_rows]

    @property
    def status_change_rows(self) -> List[StatusChangeRow]:
        all_sc_rows = self.find_elements_by_class_name("request-status-change-row")
        return [StatusChangeRow(row) for row in all_sc_rows]

    @property
    def no_requests_row(self) -> WebElement:
        return self.find_element_by_class_name("request-dne")


class PermissionRequestUpdatePage(BasePage):
    @property
    def form(self) -> WebElement:
        return self.find_element_by_id("update-form")

    def set_status(self, status: str) -> None:
        field = Select(self.form.find_element_by_name("status"))
        field.select_by_value(status)

    def set_reason(self, reason: str) -> None:
        field = self.form.find_element_by_name("reason")
        field.send_keys(reason)

    def submit(self) -> None:
        self.form.submit()


class RequestViewRow(BaseElement):
    @property
    def modify_link(self) -> str:
        modify = self.find_element_by_class_name("request-modify")
        link = modify.find_element_by_tag_name("a")
        return link.get_attribute("href")

    @property
    def requested(self) -> str:
        return self.find_element_by_class_name("request-requested").text

    @property
    def approvers(self) -> str:
        return self.find_element_by_class_name("request-approvers").text

    @property
    def status(self) -> str:
        return self.find_element_by_class_name("request-status").text

    @property
    def requested_at(self) -> str:
        return self.find_element_by_class_name("request-requested-at").text

    def click_modify_link(self) -> None:
        modify = self.find_element_by_class_name("request-modify")
        link = modify.find_element_by_tag_name("a")
        link.click()


class StatusChangeRow(BaseElement):
    @property
    def group(self) -> str:
        return self.find_element_by_class_name("request-group").text

    @property
    def who(self) -> str:
        return self.find_element_by_class_name("request-who").text

    @property
    def reason(self) -> str:
        return self.find_element_by_class_name("request-reason").text
