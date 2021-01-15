"""Data transfer object conveying a pagination request.

Pagination is handled at the repository layer since it may done via SQL, so has to be passed from
the UI through the use case to the service and repository.  Pagination is a data transfer object
holding a generic sorting and pagination request.  It should be parameterized with the type of the
sort key, which is an enum specific to a given use case.

PaginatedList is the corresponding generic type for the value returned by the repository, holding a
list of some other entity along with the total entity count and information about the pagination.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from typing import List, Optional

T = TypeVar("T")


@dataclass(frozen=True)
class Pagination(Generic[T]):
    """Type for a pagination request.

    Attributes:
        sort_key: Enum instance representing the key on which to sort
        reverse_sort: Whether to do an ascending (False) or descending (True) sort
        offset: Offset from start of sorted list
        limit: Total number of items to return
    """

    sort_key: T
    reverse_sort: bool
    offset: int
    limit: Optional[int]


@dataclass(frozen=True)
class PaginatedList(Generic[T]):
    """Type for a paginated list.

    Attributes:
        values: The members of the list
        total: Total number of list members were no pagination done
        offset: Offset from start of sorted list
        limit: Requested limit on total number of items to return (actual items may be fewer)
    """

    values: List[T]
    total: int
    offset: int
    limit: Optional[int]


# Define specific types used for pagination here, as they must be available throughout the layers.


class ListPermissionsSortKey(Enum):
    NONE = "none"
    NAME = "name"
    DATE = "date"


class PermissionGroupGrantSortKey(Enum):
    NONE = "none"
    GROUP = "group"


class PermissionServiceAccountGrantSortKey(Enum):
    NONE = "none"
    SERVICE_ACCOUNT = "service_account"
