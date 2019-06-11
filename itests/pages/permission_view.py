from typing import TYPE_CHECKING

from itests.pages.base import BaseElement, BaseModal, BasePage

if TYPE_CHECKING:
    from typing import List, Optional


class PermissionViewPage(BasePage):
    @property
    def description(self):
        # type: () -> Optional[str]
        descriptions = self.find_elements_by_class_name("permission-description")
        return descriptions[0].text if descriptions else None

    @property
    def has_audited_warning(self):
        # type: () -> bool
        return self.find_elements_by_class_name("audited-warning") != []

    @property
    def has_disabled_warning(self):
        # type: () -> bool
        return self.find_elements_by_class_name("disabled-warning") != []

    @property
    def has_disable_auditing_button(self):
        # type: () -> bool
        return self.find_elements_by_class_name("disable-auditing") != []

    @property
    def has_disable_permission_button(self):
        # type: () -> bool
        return self.find_elements_by_class_name("disable-permission") != []

    @property
    def has_enable_auditing_button(self):
        # type: () -> bool
        return self.find_elements_by_class_name("enable-auditing") != []

    @property
    def has_no_group_grants(self):
        # type: () -> bool
        return self.find_elements_by_class_name("no-group-grants") != []

    @property
    def has_no_service_account_grants(self):
        # type: () -> bool
        return self.find_elements_by_class_name("no-service-grants") != []

    @property
    def group_permission_grant_rows(self):
        # type: () -> List[PermissionGroupGrantRow]
        all_permission_grant_rows = self.find_elements_by_class_name("group-grant-row")
        return [PermissionGroupGrantRow(row) for row in all_permission_grant_rows]

    @property
    def service_account_permission_grant_rows(self):
        # type: () -> List[PermissionServiceAccountGrantRow]
        all_permission_grant_rows = self.find_elements_by_class_name("service-grant-row")
        return [PermissionServiceAccountGrantRow(row) for row in all_permission_grant_rows]

    def click_disable_auditing_button(self):
        # type: () -> None
        button = self.find_element_by_class_name("disable-auditing")
        button.click()

    def click_enable_auditing_button(self):
        # type: () -> None
        button = self.find_element_by_class_name("enable-auditing")
        button.click()

    def click_disable_permission_button(self):
        # type: () -> None
        button = self.find_element_by_class_name("disable-permission")
        button.click()

    def get_disable_auditing_modal(self):
        # type: () -> DisableAuditingModal
        element = self.find_element_by_id("disableAuditingModal")
        self.wait_until_visible(element)
        return DisableAuditingModal(element)

    def get_enable_auditing_modal(self):
        # type: () -> EnableAuditingModal
        element = self.find_element_by_id("enableAuditingModal")
        self.wait_until_visible(element)
        return EnableAuditingModal(element)

    def get_disable_permission_modal(self):
        # type: () -> DisablePermissionModal
        element = self.find_element_by_id("disablePermModal")
        self.wait_until_visible(element)
        return DisablePermissionModal(element)


class PermissionGroupGrantRow(BaseElement):
    @property
    def argument(self):
        # type: () -> str
        return self.find_element_by_class_name("grant-argument").text

    @property
    def group(self):
        # type: () -> str
        return self.find_element_by_class_name("grant-group").text


class PermissionServiceAccountGrantRow(BaseElement):
    @property
    def argument(self):
        # type: () -> str
        return self.find_element_by_class_name("grant-argument").text

    @property
    def service_account(self):
        # type: () -> str
        return self.find_element_by_class_name("grant-service").text


class DisableAuditingModal(BaseModal):
    pass


class EnableAuditingModal(BaseModal):
    pass


class DisablePermissionModal(BaseModal):
    pass
