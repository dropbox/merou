class ServiceAccountNotFoundException(Exception):
    """Attempt to operate on a service account not found in the storage layer."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Service account {name} not found")
