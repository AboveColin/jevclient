"""Typed questions and answers.

Callers never index raw JSON: they build question objects and read answer objects.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# instructions and every criteria value accept a string, an object or an array. The
# model is trained to read structure, so a schema or a database row can go in as JSON
# rather than being flattened into a sentence first.
type EntryType = str | Mapping[str, Any] | Sequence[Any] | None

from .const import (
    IMAGE_FORMATS,
    MAX_CHOICE_OPTIONS,
    MAX_IMAGE_BYTES,
    MAX_SCORE_LEVELS,
    MIN_CHOICE_OPTIONS,
    MIN_SCORE_LEVELS,
)
from .exceptions import JevResponseError


@dataclass(slots=True)
class Noul:
    """A yes/no question. The answer is the probability that the answer is yes."""

    instructions: EntryType
    true: EntryType = None
    false: EntryType = None

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "noul", "instructions": self.instructions}
        if self.true is not None or self.false is not None:
            payload["criteria"] = {"true": self.true or "", "false": self.false or ""}
        return payload


@dataclass(slots=True)
class Choice:
    """Pick one option. `criteria` maps an option name to its rubric, or to None."""

    instructions: EntryType
    criteria: Mapping[str, EntryType]

    def __post_init__(self) -> None:
        if not MIN_CHOICE_OPTIONS <= len(self.criteria) <= MAX_CHOICE_OPTIONS:
            raise ValueError(
                f"a choice takes {MIN_CHOICE_OPTIONS} to {MAX_CHOICE_OPTIONS} "
                f"options, got {len(self.criteria)}: {list(self.criteria)[:10]}"
            )

    def as_payload(self) -> dict[str, Any]:
        return {
            "type": "choice",
            "instructions": self.instructions,
            "criteria": dict(self.criteria),
        }


@dataclass(slots=True)
class Score:
    """Rate against ordered levels. The answer may fall between two levels."""

    instructions: EntryType
    criteria: Sequence[EntryType]

    def __post_init__(self) -> None:
        if not MIN_SCORE_LEVELS <= len(self.criteria) <= MAX_SCORE_LEVELS:
            raise ValueError(
                f"a score takes {MIN_SCORE_LEVELS} to {MAX_SCORE_LEVELS} levels, "
                f"got {len(self.criteria)}: {list(self.criteria)}"
            )

    def as_payload(self) -> dict[str, Any]:
        return {
            "type": "score",
            "instructions": self.instructions,
            "criteria": list(self.criteria),
        }


@dataclass(slots=True)
class Box:
    """Where something is in an image. Needs Jev 1.14 or later and an image asset.

    `instructions` names the target and the image, such as "the parcel in `door`".
    A Box takes no criteria. It always answers with a box, even when the target is
    absent, so ask a Noul beside it when the target may not be there.
    """

    instructions: EntryType

    def as_payload(self) -> dict[str, Any]:
        return {"type": "box", "instructions": self.instructions}


Question = Noul | Choice | Score | Box


@dataclass(slots=True)
class Image:
    """One PNG or JPEG, sent in the request's `assets` under a reference string.

    The client sends it base64-encoded in the JSON body, which makes it about a
    third larger on the wire. Resizing is the caller's job: the API rejects a side
    under 280 or over 1568 pixels rather than scaling it.
    """

    data: bytes
    format: str

    def __post_init__(self) -> None:
        self.format = self.format.lower()
        if self.format not in IMAGE_FORMATS:
            raise ValueError(f"an image is png or jpg, got {self.format!r}")
        if not self.data:
            raise ValueError("an image needs data, got 0 bytes")
        if len(self.data) > MAX_IMAGE_BYTES:
            raise ValueError(
                f"an image is at most {MAX_IMAGE_BYTES} bytes, got {len(self.data)}"
            )

    def as_payload(self) -> dict[str, Any]:
        return {
            "type": "image",
            "format": self.format,
            "data_base64": base64.b64encode(self.data).decode("ascii"),
        }


@dataclass(slots=True)
class NoulAnswer:
    """Probability from 0 to 1 that the answer is yes. Carries no confidence."""

    noul: float

    @property
    def value(self) -> float:
        return self.noul


@dataclass(slots=True)
class ChoiceAnswer:
    """The winning option, the full distribution, and a confidence from 0 to 1."""

    choice: str
    probabilities: dict[str, float]
    confidence: float

    @property
    def value(self) -> str:
        return self.choice


@dataclass(slots=True)
class ScoreAnswer:
    """A probability-weighted level index, with the legend it was scored against."""

    score: float
    legend: dict[str, str]
    probabilities: dict[str, float]
    confidence: float

    @property
    def value(self) -> float:
        return self.score

    @property
    def nearest_level(self) -> str:
        """The description of the level the score is closest to."""
        return self.legend.get(str(round(self.score)), "")

    @property
    def normalized(self) -> float:
        """The score as 0 to 1, whatever the number of levels.

        A score runs from 0 to len(levels) - 1, so two rubrics of different lengths
        are not comparable until they are divided by their own top level. Weighted
        composites get this wrong constantly.
        """
        top = max(len(self.legend) - 1, 1)
        return self.score / top


@dataclass(slots=True)
class BoxAnswer:
    """The four edges of the target, each a fraction of the image from 0 to 1.

    `left` and `right` are fractions of the width, `top` and `bottom` of the height,
    measured from the top-left corner.
    """

    top: float
    bottom: float
    left: float
    right: float
    confidence: float

    @property
    def value(self) -> tuple[float, float, float, float]:
        """The edges as (left, top, right, bottom), the order Pillow crops in."""
        return (self.left, self.top, self.right, self.bottom)


Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer | BoxAnswer


@dataclass(slots=True)
class Usage:
    """Token counts the API reports. Output tokens are billed at zero."""

    input_tokens: int
    output_tokens: int


@dataclass(slots=True)
class JevResponse:
    """One answered request."""

    model: str
    answers: dict[str, Answer] = field(default_factory=dict)
    usage: Usage = field(default_factory=lambda: Usage(0, 0))
    latency_ms: float = 0.0

    def __getitem__(self, key: str) -> Answer:
        return self.answers[key]


def parse_answer(key: str, raw: Mapping[str, Any]) -> Answer:
    """Turn one answer object into its typed form."""
    kind = raw.get("type")
    try:
        if kind == "noul":
            return NoulAnswer(noul=float(raw["noul"]))
        if kind == "choice":
            return ChoiceAnswer(
                choice=str(raw["choice"]),
                probabilities={k: float(v) for k, v in raw["probabilities"].items()},
                confidence=float(raw["confidence"]),
            )
        if kind == "score":
            return ScoreAnswer(
                score=float(raw["score"]),
                legend={str(k): str(v) for k, v in raw.get("legend", {}).items()},
                probabilities={
                    str(k): float(v) for k, v in raw["probabilities"].items()
                },
                confidence=float(raw["confidence"]),
            )
        if kind == "box":
            edges = raw["box"]
            return BoxAnswer(
                top=float(edges["top"]),
                bottom=float(edges["bottom"]),
                left=float(edges["left"]),
                right=float(edges["right"]),
                confidence=float(raw["confidence"]),
            )
    except (KeyError, TypeError, ValueError) as err:
        raise JevResponseError(f"answer {key!r} is not readable: {err}") from err
    raise JevResponseError(f"answer {key!r} has unknown type {kind!r}")
