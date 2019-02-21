from typing import TYPE_CHECKING

from grouper.usecases.interfaces import Transaction, TransactionInterface

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.repositories.checkpoint import CheckpointRepository
    from types import TracebackType
    from typing import Optional


class SQLTransaction(Transaction):
    """Returned by the TransactionService context manager."""

    def __init__(self, session, checkpoint_repository):
        # type: (Session, CheckpointRepository) -> None
        self.session = session
        self.checkpoint_repository = checkpoint_repository

    def __enter__(self):
        # type: () -> None
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        # type: (Optional[type], Optional[Exception], Optional[TracebackType]) -> bool
        if exc_type:
            self.session.rollback()
        else:
            try:
                self.checkpoint_repository.update_checkpoint()
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        return False


class TransactionService(TransactionInterface):
    """Manage storage layer transactions encompassing multiple service actions."""

    def __init__(self, session, checkpoint_repository):
        # type: (Session, CheckpointRepository) -> None
        self.session = session
        self.checkpoint_repository = checkpoint_repository

    def commit(self):
        # type: () -> None
        """Provided for tests, do not use in use cases."""
        self.checkpoint_repository.update_checkpoint()
        self.session.commit()

    def transaction(self):
        # type: () -> Transaction
        return SQLTransaction(self.session, self.checkpoint_repository)
