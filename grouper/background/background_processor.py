from collections import defaultdict
from contextlib import closing
from datetime import datetime
import logging
import os
from time import sleep
from typing import TYPE_CHECKING

from sqlalchemy import and_

from grouper import stats
from grouper.audit import get_auditors_group
from grouper.constants import PERMISSION_AUDITOR
from grouper.email_util import (
    notify_edge_expiration,
    notify_nonauditor_promoted,
    process_async_emails
)
from grouper.graph import Graph
from grouper.models.base.session import Session
from grouper.models.group import Group
from grouper.models.group_edge import APPROVER_ROLE_INDICES, GroupEdge
from grouper.models.user import User
from grouper.models.user_token import UserToken  # noqa: F401
from grouper.perf_profile import prune_old_traces
from grouper.util import get_database_url

if TYPE_CHECKING:
    from grouper.settings import Settings  # noqa: F401
    from grouper.error_reporting import SentryProxy  # noqa: F401
    from typing import Dict, Set  # noqa: F401


class BackgroundProcessor(object):
    """Background process for running periodic tasks.

    Currently, this sends asynchronous mail messages and handles edge expiration and notification.
    """

    def __init__(self, settings, sentry_client):
        # type: (Settings, SentryProxy) -> None
        """Initialize new BackgroundProcessor"""

        self.settings = settings
        self.sentry_client = sentry_client
        self.logger = logging.getLogger(__name__)

    def _capture_exception(self):
        if self.sentry_client:
            self.sentry_client.captureException()

    def crash(self):
        os._exit(1)

    def expire_edges(self, session):
        # type: (Session) -> None
        """Mark expired edges as inactive and log to the audit log.

        Edges are immediately excluded from the permission graph once they've
        expired, but we also want to note the expiration in the audit log and send
        an email notification.  This function finds all expired edges, logs the
        expiration to the audit log, and sends a notification message.  It's meant
        to be run from the background processing thread.
        """
        now = datetime.utcnow()

        # Pull the expired edges.
        edges = session.query(GroupEdge).filter(
            GroupEdge.group_id == Group.id,
            Group.enabled == True,
            GroupEdge.active == True,
            and_(
                GroupEdge.expiration <= now,
                GroupEdge.expiration != None
            )
        ).all()

        # Expire each one.
        for edge in edges:
            notify_edge_expiration(self.settings, session, edge)
            edge.active = False
            session.commit()

    def promote_nonauditors(self, session):
        # type: (Session) -> None
        """Checks all enabled audited groups and ensures that all approvers for that group have
        the PERMISSION_AUDITOR permission. All non-auditor approvers of audited groups will be
        promoted to be auditors, i.e., added to the auditors group.

        Args:
            session (Session): database session
        """
        graph = Graph()
        # Hack to ensure the graph is loaded before we access it
        graph.update_from_db(session)
        # map from user object to names of audited groups in which
        # user is a nonauditor approver
        nonauditor_approver_to_groups = defaultdict(set)  # type: Dict[User, Set[str]]
        user_is_auditor = {}  # type: Dict[str, bool]
        for group_tuple in graph.get_groups(audited=True, directly_audited=False):
            group_md = graph.get_group_details(group_tuple.groupname, expose_aliases=False)
            for username, user_md in group_md['users'].items():
                if username not in user_is_auditor:
                    user_perms = graph.get_user_details(username)['permissions']
                    user_is_auditor[username] = any(
                        [p['permission'] == PERMISSION_AUDITOR for p in user_perms])
                if user_is_auditor[username]:
                    # user is already auditor so can skip
                    continue
                if user_md['role'] in APPROVER_ROLE_INDICES:
                    # non-auditor approver. BAD!
                    nonauditor_approver_to_groups[username].add(group_tuple.groupname)

        if nonauditor_approver_to_groups:
            auditors_group = get_auditors_group(session)
            for username, group_names in nonauditor_approver_to_groups.items():
                reason = 'auto-added due to having approver role(s) in group(s): {}'.format(
                    ', '.join(group_names))
                user = User.get(session, name=username)
                auditors_group.add_member(user, user, reason, status="actioned")
                notify_nonauditor_promoted(
                    self.settings, session, user, auditors_group, group_names)

        session.commit()

    def run(self):
        # type: () -> None
        initial_url = get_database_url(self.settings)
        while True:
            try:
                if get_database_url(self.settings) != initial_url:
                    self.crash()
                with closing(Session()) as session:
                    self.logger.info("Expiring edges....")
                    self.expire_edges(session)

                    self.logger.info("Promoting nonauditor approvers in audited groups...")
                    self.promote_nonauditors(session)

                    self.logger.info("Sending emails...")
                    process_async_emails(self.settings, session, datetime.utcnow())

                    self.logger.info("Pruning old traces....")
                    prune_old_traces(session)

                    session.commit()

                stats.log_gauge("successful-background-update", 1)
                stats.log_gauge("failed-background-update", 0)
            except:
                stats.log_gauge("successful-background-update", 0)
                stats.log_gauge("failed-background-update", 1)
                self._capture_exception()
                self.logger.exception("Unexpected exception occurred in background thread.")
                self.crash()

            self.logger.debug("Sleeping for {} seconds...".format(self.settings.sleep_interval))
            sleep(self.settings.sleep_interval)
