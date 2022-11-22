import re

from grouper.log_redact import RedactingFormatter


def test_redact_regex() -> None:
    """Test regular expressions compile correctly."""
    for pattern in RedactingFormatter._REDACT_PATTERNS:
        re.compile(pattern.regex)


def test_known_bad_strings() -> None:
    """Test the redaction filter on known sensitive log strings.

    The actual value of the password in each sample is replaced
    with the string "PASSWORD".
    """
    bad_strings = [
        "mysql://grouper:PASSWORD@localhost:3306/grouper",
        "mysql://localhost:3306?username=grouper&password=PASSWORD"
        "sqlite:////srv/grouper.db?password=PASSWORD",
    ]

    redactor = RedactingFormatter()

    for sample in bad_strings:
        filtered = redactor._redact(sample)
        assert "PASSWORD" not in filtered
