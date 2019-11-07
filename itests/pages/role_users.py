from __future__ import annotations

from itests.pages.base import BaseModal, BasePage


class RoleUserViewPage(BasePage):
    def click_disable_button(self) -> None:
        button = self.find_element_by_id("disable-role-user")
        button.click()

    def get_disable_modal(self) -> DisableRoleUserModal:
        element = self.find_element_by_id("disableModal")
        self.wait_until_visible(element)
        return DisableRoleUserModal(element)


class DisableRoleUserModal(BaseModal):
    pass
