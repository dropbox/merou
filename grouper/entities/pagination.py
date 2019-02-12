"""Data transfer object conveying a pagination request.

Pagination is handled at the repository layer since it may done via SQL, so has to be passed from
the UI through the use case to the service and repository.  Pagination is a data transfer object
holding a generic sorting and pagination request.  It should be parameterized with the type of the
sort key, which is an enum specific to a given use case.

PaginatedList is the corresponding generic type for the value returned by the repository, holding a
list of some other entity along with the total entity count and information about the pagination.
"""

from typing import Generic, List, Optional, TypeVar

T = TypeVar("T")


class Pagination(Generic[T]):
    """Type for a pagination request.

    Attributes:
        sort_key: Enum instance representing the key on which to sort
        reverse_sort: Whether to do an ascending (False) or descending (True) sort
        offset: Offset from start of sorted list
        limit: Total number of items to return
    """

    def __init__(self, sort_key, reverse_sort, offset, limit):
        # type: (T, bool, int, Optional[int]) -> None
        self.sort_key = sort_key
        self.reverse_sort = reverse_sort
        self.offset = offset
        self.limit = limit


class PaginatedList(Generic[T]):
    """Type for a paginated list.

    Attributes:
        values: The members of the list
        total: Total number of list members were no pagination done
        offset: Offset from start of sorted list
    """

    def __init__(self, values, total, offset):
        # type: (List[T], int, int) -> None
        self.values = values
        self.total = total
        self.offset = offset
