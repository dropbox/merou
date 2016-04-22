from datetime import datetime

from enum import IntEnum
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, or_, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import relationship

from grouper.models.base.model_base import Model
from grouper.plugin import get_plugins


class AuditLogCategory(IntEnum):
    """Categories of entries in the audit_log."""

    # generic, catch-all category
    general = 1

    # periodic global audit related
    audit = 2


class AuditLogFailure(Exception):
    pass


class AuditLog(Model):
    '''
    Logs actions taken in the system. This is a pretty simple logging framework to just
    let us track everything that happened. The main use case is to show users what has
    happened recently, to help them understand.
    '''

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    log_time = Column(DateTime, default=datetime.utcnow, nullable=False)

    # The actor is the person who took an action.
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor = relationship("User", foreign_keys=[actor_id])

    # The 'on_*' columns are what was acted on.
    on_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    on_user = relationship("User", foreign_keys=[on_user_id])
    on_group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    on_group = relationship("Group", foreign_keys=[on_group_id])
    on_permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=True)
    on_permission = relationship("Permission", foreign_keys=[on_permission_id])

    # The action and description columns are text. These are mostly displayed
    # to the user as-is, but we might provide filtering or something.
    action = Column(String(length=64), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Integer, nullable=False, default=AuditLogCategory.general)

    @staticmethod
    def log(session, actor_id, action, description,
            on_user_id=None, on_group_id=None, on_permission_id=None,
            category=AuditLogCategory.general):
        '''
        Log an event in the database.

        Args:
            session(Session): database session
            actor_id(int): actor
            action(str): unique string identifier for action taken
            description(str): description for action taken
            on_user_id(int): user affected, if any
            on_group_id(int): group affected, if any
            on_permission_id(int): permission affected, if any
            category(AuditLogCategory): category of log entry
        '''
        entry = AuditLog(
            actor_id=actor_id,
            log_time=datetime.utcnow(),
            action=action,
            description=description,
            on_user_id=on_user_id if on_user_id else None,
            on_group_id=on_group_id if on_group_id else None,
            on_permission_id=on_permission_id if on_permission_id else None,
            category=int(category),
        )
        try:
            entry.add(session)
            session.flush()
        except IntegrityError:
            session.rollback()
            raise AuditLogFailure()
        session.commit()

        for plugin in get_plugins():
            plugin.log_auditlog_entry(entry)

    @staticmethod
    def get_entries(session, actor_id=None, on_user_id=None, on_group_id=None,
                    on_permission_id=None, limit=None, offset=None, involve_user_id=None,
                    category=None, action=None):
        '''
        Flexible method for getting log entries. By default it returns all entries
        starting at the newest. Most recent first.

        involve_user_id, if set, is (actor_id OR on_user_id).
        '''

        results = session.query(AuditLog)

        if actor_id:
            results = results.filter(AuditLog.actor_id == actor_id)
        if on_user_id:
            results = results.filter(AuditLog.on_user_id == on_user_id)
        if on_group_id:
            results = results.filter(AuditLog.on_group_id == on_group_id)
        if on_permission_id:
            results = results.filter(AuditLog.on_permission_id == on_permission_id)
        if involve_user_id:
            results = results.filter(or_(
                AuditLog.on_user_id == involve_user_id,
                AuditLog.actor_id == involve_user_id
            ))
        if category:
            results = results.filter(AuditLog.category == int(category))
        if action:
            results = results.filter(AuditLog.action == action)

        results = results.order_by(desc(AuditLog.log_time))

        if offset:
            results = results.offset(offset)
        if limit:
            results = results.limit(limit)

        return results.all()
