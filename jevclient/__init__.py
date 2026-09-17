"""Async client for TypeSafe's Jev, the System One decision model.

Jev answers typed questions about a state and returns values, not prose. The three
question types are Noul (a yes/no probability), Choice (one option out of a set,
with the full distribution) and Score (a rating against ordered levels).
"""

from .client import JevClient
from .const import DEFAULT_BASE_URL, DEFAULT_MODEL, USD_PER_MILLION_INPUT_TOKENS
from .exceptions import (
    JevAuthError,
    JevConnectionError,
    JevError,
    JevOverloadedError,
    JevRateLimitError,
    JevResponseError,
    JevValidationError,
)
from .models import (
    Answer,
    Choice,
    ChoiceAnswer,
    JevResponse,
    Noul,
    NoulAnswer,
    Question,
    Score,
    ScoreAnswer,
    Usage,
)

__version__ = "1.0.0"

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "USD_PER_MILLION_INPUT_TOKENS",
    "Answer",
    "Choice",
    "ChoiceAnswer",
    "JevAuthError",
    "JevClient",
    "JevConnectionError",
    "JevError",
    "JevOverloadedError",
    "JevRateLimitError",
    "JevResponse",
    "JevResponseError",
    "JevValidationError",
    "Noul",
    "NoulAnswer",
    "Question",
    "Score",
    "ScoreAnswer",
    "Usage",
    "__version__",
]
