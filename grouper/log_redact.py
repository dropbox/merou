import logging
import re
from dataclasses import dataclass


@dataclass
class RedactionPattern:
    # regular expression to match for redaction
    regex: str
    # sensitive string will be replaced by this "redacted_message" in the log output
    redacted_message: str


class RedactingFormatter(logging.Formatter):
    """RedactingFormatter masks sensitive regular expressions from log entries."""

    _REDACT_PATTERNS = [
        RedactionPattern(  # mysql url
            r"mysql://\S*",
            "DB_URL_REDACTED",
        ),
        RedactionPattern(  # sqlite url
            r"sqlite://\S*",
            "DB_URL_REDACTED",
        ),
        RedactionPattern(  # anything with password=
            r"password=\S+",
            "PASSWORD_REDACTED",
        ),
    ]

    def _redact(self, log_string: str) -> str:
        new_string = log_string
        for pattern in RedactingFormatter._REDACT_PATTERNS:
            new_string = re.sub(
                pattern.regex,
                f"<{pattern.redacted_message}>",
                new_string,
                flags=re.IGNORECASE,
            )
        return new_string

    def format(self, record: logging.LogRecord) -> str:
        original_log_message = super().format(record)
        return self._redact(original_log_message)
