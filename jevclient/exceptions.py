"""Exceptions raised by the client.

Every HTTP status the API documents maps to its own class, so callers can retry a
529 and re-authenticate a 401 without parsing strings.
"""


class JevError(Exception):
    """Base class for every error this library raises."""


class JevConnectionError(JevError):
    """The request never reached the API, or the reply never arrived."""


class JevAuthError(JevError):
    """HTTP 401. The API key is missing, wrong, or revoked."""


class JevValidationError(JevError):
    """HTTP 422. The request was malformed; the message names the field at fault."""


class JevRateLimitError(JevError):
    """HTTP 429. Back off before retrying."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class JevOverloadedError(JevError):
    """HTTP 529. The service is saturated; retry shortly."""


class JevResponseError(JevError):
    """The API answered with a body this library cannot read."""
