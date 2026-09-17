"""Typed questions and answers.

Callers never index raw JSON: they build question objects and read answer objects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .exceptions import JevResponseError


@dataclass(slots=True)
class Noul:
    """A yes/no question. The answer is the probability that the answer is yes."""

    instructions: str
    true: str | None = None
    false: str | None = None

    def as_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "noul", "instructions": self.instructions}
        if self.true is not None or self.false is not None:
            payload["criteria"] = {"true": self.true or "", "false": self.false or ""}
        return payload


@dataclass(slots=True)
class Choice:
    """Pick one option. `criteria` maps an option name to its rubric, or to None."""

    instructions: str
    criteria: Mapping[str, str | None]

    def __post_init__(self) -> None:
        if len(self.criteria) < 2:
            raise ValueError(
                f"a choice needs at least 2 options, got {len(self.criteria)}: "
                f"{list(self.criteria)}"
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

    instructions: str
    criteria: Sequence[str]

    def __post_init__(self) -> None:
        if len(self.criteria) < 2:
            raise ValueError(
                f"a score needs at least 2 levels, got {len(self.criteria)}: "
                f"{list(self.criteria)}"
            )

    def as_payload(self) -> dict[str, Any]:
        return {
            "type": "score",
            "instructions": self.instructions,
            "criteria": list(self.criteria),
        }


Question = Noul | Choice | Score


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


Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer


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
                probabilities={str(k): float(v) for k, v in raw["probabilities"].items()},
                confidence=float(raw["confidence"]),
            )
    except (KeyError, TypeError, ValueError) as err:
        raise JevResponseError(f"answer {key!r} is not readable: {err}") from err
    raise JevResponseError(f"answer {key!r} has unknown type {kind!r}")
