
class Error(Exception):
    """ Baseclass for Grouper Exceptions."""


class ModelError(Error):
    """ Baseclass for errors at the Model layer."""


class GraphError(Error):
    """ Baseclass for errors at the Model layer."""


class NoSuchUser(GraphError):
    """ Raised when groups are requested for a user that doesn't exist."""


class NoSuchGroup(GraphError):
    """ Raised when users are requested for a group that doesn't exist."""
