"""Async client for TypeSafe's Jev, the System One decision model.

Jev answers typed questions about a state and returns values, not prose. The four
question types are Noul (a yes/no probability), Choice (one option out of a set,
with the full distribution), Score (a rating against ordered levels) and Box (where
something is in an image, Jev 1.14 and later).
"""

from .client import JevClient
from .const import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    IMAGES_HEADER,
    MAX_CHOICE_OPTIONS,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_SIDE,
    MAX_SCORE_LEVELS,
    MIN_CHOICE_OPTIONS,
    MIN_IMAGE_SIDE,
    MIN_SCORE_LEVELS,
    USD_PER_MILLION_INPUT_TOKENS,
)
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
    Box,
    BoxAnswer,
    Choice,
    ChoiceAnswer,
    EntryType,
    Image,
    JevResponse,
    Noul,
    NoulAnswer,
    Question,
    Score,
    ScoreAnswer,
    Usage,
)

__version__ = "1.3.0"

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "IMAGES_HEADER",
    "MAX_CHOICE_OPTIONS",
    "MAX_IMAGE_BYTES",
    "MAX_IMAGE_SIDE",
    "MAX_SCORE_LEVELS",
    "MIN_CHOICE_OPTIONS",
    "MIN_IMAGE_SIDE",
    "MIN_SCORE_LEVELS",
    "USD_PER_MILLION_INPUT_TOKENS",
    "Answer",
    "Box",
    "BoxAnswer",
    "Choice",
    "ChoiceAnswer",
    "EntryType",
    "Image",
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
