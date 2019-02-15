from itests.pages.base import BasePage


class AuditsCreatePage(BasePage):
    def _get_new_audit_form(self):
        return self.find_element_by_class_name("new-audit-form")

    def set_end_date(self, end_date):
        form = self._get_new_audit_form()
        field = form.find_element_by_name("ends_at")
        field.send_keys(end_date)

    def submit(self):
        form = self._get_new_audit_form()
        form.submit()
