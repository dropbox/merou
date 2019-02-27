from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_checkpoint_update(setup):
    # type: (SetupTest) -> None
    """Test that the updates counter is incremented at the end of each transaction commit."""
    checkpoint_repository = setup.repository_factory.create_checkpoint_repository()
    checkpoint = checkpoint_repository.get_checkpoint()
    assert checkpoint.checkpoint == 0

    transaction_service = setup.service_factory.create_transaction_service()
    with transaction_service.transaction():
        checkpoint = checkpoint_repository.get_checkpoint()
        assert checkpoint.checkpoint == 0

    checkpoint = checkpoint_repository.get_checkpoint()
    assert checkpoint.checkpoint == 1
