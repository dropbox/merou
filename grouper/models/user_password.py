from datetime import datetime
import hashlib
import hmac
import os

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from grouper.models.base.model_base import Model


def _make_salt():
    return os.urandom(20).encode("hex")


class UserPassword(Model):
    """Simple password hashes stored to a user for use by thirdparty applications"""

    __tablename__ = "user_passwords"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(length=16), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    disabled_at = Column(DateTime, default=None, nullable=True)

    _hashed_secret = Column(Text, nullable=False)
    salt = Column(String(length=128), nullable=False)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "name"),
    )

    @staticmethod
    def get(session, user, name=None, id=None):
        """Retrieves a single UserPassword.

        Args:
            session (Session): Session object
            user (User): Owner of the password
            name (str): Name of the password
            id (int): Primary key of the password

        Returns:
            UserPassword: UserPassword matching the specified constraints

        """
        assert name is None or id is None

        if name is not None:
            return session.query(UserPassword).filter_by(name=name, user=user).scalar()
        return session.query(UserPassword).filter_by(id=id, user=user).scalar()

    @property
    def password(self):
        return self._hashed_secret

    @password.setter
    def password(self, new_password):
        self.salt = _make_salt()
        self._hashed_secret = hashlib.sha512(new_password + self.salt).hexdigest()

    def check_password(self, password_to_check):
        h = hashlib.sha512(password_to_check + self.salt).hexdigest()
        return self.check_hash(h)

    def check_hash(self, hash_to_check):
        return self.enabled and hmac.compare_digest(
                hash_to_check,
                self.password.encode('utf-8'),
        )

    @property
    def enabled(self):
        return self.disabled_at is None and self.user.enabled

    def __str__(self):
        return "/".join((
                self.user.username if self.user is not None else "unspecified",
                self.name if self.name is not None else "unspecified",
        ))
