from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from grouper.constants import MAX_NAME_LENGTH
from grouper.models.base.model_base import Model


class AsyncNotification(Model):
    """Represent a notification tracking/sending mechanism"""

    __tablename__ = "async_notifications"

    id = Column(Integer, primary_key=True)
    key = Column(String(length=MAX_NAME_LENGTH))

    email = Column(String(length=MAX_NAME_LENGTH), nullable=False)
    subject = Column(String(length=256), nullable=False)
    body = Column(Text, nullable=False)
    send_after = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False, nullable=False)
