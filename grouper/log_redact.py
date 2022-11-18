from dataclasses import dataclass
import logging
import re

@dataclass
class RedactionPattern:
    # regular expression to match for redaction
    regex: str
    # sensitive string will be replaced by this "redacted_message" in the log output
    redacted_message: str

class RedactingFormatter(logging.Formatter):
    """
    RedactingFormatter masks sensitive regular expressions from log entries.
    
    Configure the sensitive log regular expressions in settings.log_redact_patterns.
    """

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

    def _filter(self, log_string: str) -> str:
        new_string = log_string
        for pattern in RedactingFormatter._REDACT_PATTERNS:
            new_string = re.sub(pattern.regex, f"<{pattern.redacted_message}>", new_string)
        return new_string
    
    def format(self, record: logging.LogRecord) -> str:
        original_log_message = logging.Formatter.format(self, record)
        return self._filter(original_log_message)
