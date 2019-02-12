from typing import TYPE_CHECKING

from grouper.usecases.interfaces import TransactionInterface

if TYPE_CHECKING:
    from grouper.models.base.session import Session


class TransactionService(TransactionInterface):
    """Manage storage layer transactions encompassing multiple service actions."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def start_transaction(self):
        # type: () -> None
        pass

    def commit(self):
        # type: () -> None
        self.session.commit()
