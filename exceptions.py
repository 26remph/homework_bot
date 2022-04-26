class LoadEnvironmentError(Exception):
    """Exception environment."""

    pass


class APIResponseError(Exception):
    """Exception request url endpoints."""

    pass


class SendMessageError(Exception):
    """Exception delivery message in service."""

    pass


# class ResponseStatusCodeError(Exception):
#     """Exception response."""
#
#     pass


class JSONDataStructureError (Exception):
    """Exception JSON Data structure."""

    pass


class UndocumentedStatusError(Exception):
    """Recive undocumented statuds homework."""

    pass


# class StateStatusException(Exception):
#     """Exception for state homework status."""
#
#     pass
