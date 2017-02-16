from contextlib import closing
from datetime import datetime, timedelta
import logging
from threading import Thread
from time import sleep

from expvar.stats import stats
from sqlalchemy import and_
from sqlalchemy.exc import OperationalError

from grouper.constants import PERMISSION_AUDITOR
from grouper.email_util import (
    notify_edge_expiration,
    notify_nonauditor_flagged,
    process_async_emails
    )
from grouper.graph import Graph
from grouper.group import get_audited_groups
from grouper.model_soup import APPROVER_ROLE_INDICIES, Group, GroupEdge
from grouper.models.base.session import get_db_engine, Session
from grouper.models.user import User
from grouper.perf_profile import init_stopwatch, prune_old_traces
from grouper.settings import settings
from grouper.user import user_role_index
from grouper.user_permissions import user_has_permission
from grouper.util import get_database_url


class BackgroundThread(Thread):
    """Background thread for running periodic tasks.

    Currently, this sends asynchronous mail messages and handles edge expiration and notification.

    This class thread will exist on multiple servers in a standard Grouper production environment
    so we need to ensure that it's race-safe.
    """
    def __init__(self, settings, sentry_client, *args, **kwargs):
        """Initialize new BackgroundThread

        Args:
            settings (Settings): The current Settings object for this application.
        """
        self.settings = settings
        self.sentry_client = sentry_client
        self.logger = logging.getLogger(__name__)
        Thread.__init__(self, *args, **kwargs)

    def capture_exception(self):
        if self.sentry_client:
            self.sentry_client.captureException()

    def expire_edges(self, session):
        """Mark expired edges as inactive and log to the audit log.

        Edges are immediately excluded from the permission graph once they've
        expired, but we also want to note the expiration in the audit log and send
        an email notification.  This function finds all expired edges, logs the
        expiration to the audit log, and sends a notification message.  It's meant
        to be run from the background processing thread.

        Args:
            session (session): database session
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

    def expire_nonauditors(self, session):
        """Checks all enabled audited groups and ensures that all approvers for that group have
        the PERMISSION_AUDITOR permission. All approvers of audited groups that aren't auditors
        have their membership in the audited group set to expire
        settings.nonauditor_expiration_days days in the future.

        Args:
            session (Session): database session
        """
        now = datetime.utcnow()
        graph = Graph()
        exp_days = timedelta(days=settings.nonauditor_expiration_days)
        # Hack to ensure the graph is loaded before we access it
        graph.update_from_db(session)
        # TODO(tyleromeara): replace with graph call
        for group in get_audited_groups(session):
            members = group.my_members()
            # Go through every member of the group and set them to expire if they are an approver
            # but not an auditor
            for (type_, member), edge in members.iteritems():
                # Auditing is already inherited, so we don't need to handle that here
                if type_ == "Group":
                    continue
                member = User.get(session, name=member)
                member_is_approver = user_role_index(member, members) in APPROVER_ROLE_INDICIES
                member_is_auditor = user_has_permission(session, member, PERMISSION_AUDITOR)
                if not member_is_approver or member_is_auditor:
                    continue
                edge = GroupEdge.get(session, id=edge.edge_id)
                if edge.expiration and edge.expiration < now + exp_days:
                    continue
                exp = now + exp_days
                exp = exp.date()
                edge.apply_changes_dict(
                    {"expiration": "{}/{}/{}".format(exp.month, exp.day, exp.year)}
                )
                edge.add(session)
                notify_nonauditor_flagged(settings, session, edge)
        session.commit()

    def run(self):
        # get a new stopwatch context for this thread
        init_stopwatch()

        while True:
            try:
                with closing(Session()) as session:
                    self.logger.debug("Expiring edges....")
                    self.expire_edges(session)
                    self.logger.debug("Expiring nonauditor approvers in audited groups...")
                    self.expire_nonauditors(session)
                    self.logger.debug("Sending emails...")
                    process_async_emails(self.settings, session, datetime.utcnow())
                    self.logger.debug("Pruning old traces....")
                    prune_old_traces(session)
                    session.commit()

                stats.set_gauge("successful-background-update", 1)
                stats.set_gauge("failed-background-update", 0)
            except OperationalError:
                Session.configure(bind=get_db_engine(get_database_url(self.settings)))
                self.logger.critical("Failed to connect to database.")
                stats.set_gauge("successful-background-update", 0)
                stats.set_gauge("failed-background-update", 1)
                self.capture_exception()
            except:
                stats.set_gauge("successful-background-update", 0)
                stats.set_gauge("failed-background-update", 1)
                self.capture_exception()
                raise

            sleep(60)
