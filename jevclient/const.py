"""Endpoints and magic values for the TypeSafe API."""

from typing import Final

DEFAULT_BASE_URL: Final = "https://api.typesafe.ai"
SYSTEMONE_PATH: Final = "/v1/systemone"
DEFAULT_MODEL: Final = "jev-latest"
DEFAULT_TIMEOUT: Final = 30.0

# TypeSafe's published input price, US dollars per million input tokens. Output is
# billed at zero. Questions are billed as input tokens too, about 38 tokens for a
# short one, so a large question set is not free.
USD_PER_MILLION_INPUT_TOKENS: Final = 0.042
