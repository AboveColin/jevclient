"""Exceptions raised by the client.

Every HTTP status the API documents maps to its own class, so callers can retry a
529 and re-authenticate a 401 without parsing strings.
"""


class JevError(Exception):
    """Base class for every error this library raises.

    `status` is the HTTP status the API answered with, and None when the request
    never got an answer or the answer could not be read.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class JevConnectionError(JevError):
    """The request never reached the API, or the reply never arrived."""


class JevAuthError(JevError):
    """HTTP 401. The API key is missing, wrong, or revoked."""


class JevValidationError(JevError):
    """HTTP 400, 413 or 422. The API refused the request as it was written.

    The message carries the API's own reason, such as "Unknown model: jev-nope" or
    "Invalid image dimensions". 413 is a request over a size limit.
    """


class JevRateLimitError(JevError):
    """HTTP 429. Back off before retrying."""

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        *,
        status: int | None = 429,
    ) -> None:
        super().__init__(message, status=status)
        self.retry_after = retry_after


class JevOverloadedError(JevError):
    """HTTP 529. The service is saturated; retry shortly."""


class JevResponseError(JevError):
    """The API answered with a body this library cannot read."""
