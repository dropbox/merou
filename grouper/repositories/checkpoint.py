from typing import TYPE_CHECKING

from grouper.entities.checkpoint import Checkpoint
from grouper.models.counter import Counter

if TYPE_CHECKING:
    from grouper.models.base.session import Session


class CheckpointRepository:
    """Manage the checkpoint counter used for graph reloading.

    On every change to any Grouper data, increment an updates counter stored in the database.  This
    triggers a graph reload in any service that has a background graph refresh thread, is returned
    by the API server in all requests, and is used by API clients to ensure that they do not use an
    older version of the graph when talking to multiple API servers.
    """

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def get_checkpoint(self):
        # type: () -> Checkpoint
        counter = self.session.query(Counter).filter_by(name="updates").scalar()
        if counter:
            return Checkpoint(counter.count, int(counter.last_modified.strftime("%s")))
        else:
            return Checkpoint(0, 0)

    def update_checkpoint(self):
        # type: () -> None
        """Update the checkpoint counter.

        We intentionally do not update the last_modified date of the counter because groupy had a
        nonsensical test for whether the checkpoint timestamp was within 600 seconds of the time of
        the API response and a bug that reversed the logic.  Therefore, if the update timestamp is
        within 600s of the current time, groupy will fail.

        This was fixed in groupy 0.3.0 in 2016, so it could probably now be re-enabled.
        """
        counter = self.session.query(Counter).filter_by(name="updates").with_for_update().scalar()
        if counter:
            counter.count += 1
        else:
            Counter(name="updates", count=1).add(self.session)
