from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from types import TracebackType
    from typing import Optional


class SQLTransaction(object):
    """Returned by a TransactionRepository as a context manager."""

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


class TransactionRepository(object):
    """Manage storage layer transactions."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def commit(self):
        # type: () -> None
        """Provided for tests, do not use in use cases."""
        self.session.commit()

    def transaction(self):
        # type: () -> SQLTransaction
        return SQLTransaction(self.session)
