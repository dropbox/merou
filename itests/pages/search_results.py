from typing import TYPE_CHECKING

from itests.pages.base import BaseElement, BasePage

if TYPE_CHECKING:
    from typing import List


class SearchResultsPage(BasePage):
    @property
    def result_rows(self):
        # type: () -> List[SearchResultRow]
        all_result_rows = self.find_elements_by_class_name("result-row")
        return [SearchResultRow(row) for row in all_result_rows]


class SearchResultRow(BaseElement):
    @property
    def type(self):
        # type: () -> str
        return self.find_element_by_class_name("result-type").text

    @property
    def name(self):
        # type: () -> str
        cell = self.find_element_by_class_name("result-name")
        return cell.find_element_by_tag_name("a").text
