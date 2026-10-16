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

# Documented limits. Checking them here turns a 422 that names a field the caller
# never wrote into a message that names the limit and the ask.
MIN_CHOICE_OPTIONS: Final = 2
MAX_CHOICE_OPTIONS: Final = 255
MIN_SCORE_LEVELS: Final = 2
MAX_SCORE_LEVELS: Final = 10

# Images and Box questions are off unless a request carries this header. Without it
# the API answers 400: "Images are experimental. Send the header
# TypeSafe-Danger-Zone-Images: true to use them." (measured 2026-10-16).
IMAGES_HEADER: Final = "TypeSafe-Danger-Zone-Images"

# Documented image limits (docs.typesafe.ai/images, read 2026-10-16). The API rejects
# an image outside them and never resizes it: a 1920 x 1080 JPEG came back 400,
# "Invalid image dimensions" (measured 2026-10-16).
MIN_IMAGE_SIDE: Final = 280
MAX_IMAGE_SIDE: Final = 1568
MAX_IMAGE_BYTES: Final = 16 * 1024 * 1024
IMAGE_FORMATS: Final = frozenset({"png", "jpg", "jpeg"})
