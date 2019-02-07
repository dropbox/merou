class Authorization(object):
    """Indicates that an action has been authorized.

    This object is a required parameter to any write action on a backend service.  This pattern is
    used so that type checking of the arguments to backend services will force use case callers to
    explicitly construct an Authorization object, and thus reduce the chances that a write action
    is allowed without authorization checks.

    Attributes:
        actor: Identity of the user performing the action
    """

    def __init__(self, actor):
        # type: (str) -> None
        self.actor = actor
