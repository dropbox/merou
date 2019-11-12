from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from types import TracebackType
    from typing import Optional
    from typing_extensions import Literal


class SQLTransaction:
    """Returned by a TransactionRepository as a context manager."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> None:
        pass

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[TracebackType],
    ) -> Literal[False]:
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
        return False


class TransactionRepository:
    """Manage storage layer transactions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def transaction(self) -> SQLTransaction:
        return SQLTransaction(self.session)
