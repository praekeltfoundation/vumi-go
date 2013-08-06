class VumiGoError(Exception):
    """An error raised by Vumi Go."""


class UnknownConversationType(VumiGoError):
    """Raised when an invalid conversation type is encountered."""


class UnknownRouterType(VumiGoError):
    """Raised when an invalid router type is encountered."""
