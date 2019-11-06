class ServiceAccountNotFoundException(Exception):
    """Attempt to operate on a service account not found in the storage layer."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "Service account {} not found".format(name)
        super().__init__(msg)
