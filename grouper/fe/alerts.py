class Alert:
    def __init__(self, severity: str, message: str, heading: str = None) -> None:
        self.severity = severity
        self.message = message
        if heading is None:
            self.heading = severity.title() + "!"
        else:
            self.heading = heading
