class LoadEnvironmentError(Exception):
    """Exception environment."""

    pass


class APIResponseError(Exception):
    """Exception request url endpoints."""

    pass


class SendMessageError(Exception):
    """Exception delivery message in service."""

    pass


class JSONDataStructureError (Exception):
    """Exception JSON Data structure."""

    pass
