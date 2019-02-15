from typing import TYPE_CHECKING

from grouper.usecases.interfaces import Transaction, TransactionInterface

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from types import TracebackType
    from typing import Optional


class SQLTransaction(Transaction):
    """Returned by the TransactionService context manager."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def __enter__(self):
        # type: () -> None
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        # type: (Optional[type], Optional[Exception], Optional[TracebackType]) -> bool
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
        return False


class TransactionService(TransactionInterface):
    """Manage storage layer transactions encompassing multiple service actions."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def commit(self):
        # type: () -> None
        """Provided for tests, do not use in use cases."""
        self.session.commit()

    def transaction(self):
        # type: () -> Transaction
        return SQLTransaction(self.session)
