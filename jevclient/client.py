"""Async client for the TypeSafe System One endpoint."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any, Self

import aiohttp

from .const import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    IMAGES_HEADER,
    SYSTEMONE_PATH,
)
from .exceptions import (
    JevAuthError,
    JevConnectionError,
    JevOverloadedError,
    JevRateLimitError,
    JevResponseError,
    JevValidationError,
)
from .models import Box, Image, JevResponse, Question, Usage, parse_answer

StateType = str | Mapping[str, Any] | list[Any]


class JevClient:
    """One client per API key.

    `api_key` may be empty, for an endpoint that speaks this API and asks for no
    credential. The Authorization header is then left off the request.

    Every question in a call is evaluated in isolation against the same state, and
    the API answers them in parallel. Measured 2026-09-17 from the Netherlands:
    3 questions took 712 ms and 100 took 714 ms, so batching questions into one
    call is close to free in time. It is not free in money, because question text
    is billed as input tokens.
    """

    def __init__(
        self,
        api_key: str,
        *,
        session: aiohttp.ClientSession | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session
        self._owns_session = session is None

    def _headers(self, *, images: bool = False) -> dict[str, str]:
        """The credential to send, when there is one, and the images switch.

        An empty key means the endpoint needs none, and then it gets no header at
        all. "Bearer " with nothing after it is not a credential: a server that
        parses the header rather than ignoring it answers 400 or 401 to it.

        The images header goes only on a request with an image or a Box question,
        because the API documents it as a per-request opt-in.
        """
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        if images:
            headers[IMAGES_HEADER] = "true"
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def ask(
        self,
        state: StateType,
        questions: Mapping[str, Question],
        *,
        model: str | None = None,
        assets: Mapping[str, Image] | None = None,
    ) -> JevResponse:
        """Evaluate every question against one state and return typed answers.

        The keys of `questions` come back as the keys of `answers`. They are not
        sent to the model and play no part in inference, so name them for your code.

        `assets` maps a reference string to an image. Write the reference where the
        image belongs, in the state, an instruction or a criterion, and the model
        receives the image there. Each place a reference appears adds the image
        again and is billed again, so put an image several questions use in the
        state once. A random UUID per image is the safest reference: the API
        matches it as plain text, so "cat" would also match inside "category".
        """
        if not questions:
            raise ValueError("ask() needs at least one question")

        payload: dict[str, Any] = {
            "state": state,
            "model": model or self._model,
            "questions": {key: q.as_payload() for key, q in questions.items()},
        }
        if assets:
            _check_references(payload, assets)
            payload["assets"] = {
                ref: image.as_payload() for ref, image in assets.items()
            }
        images = bool(assets) or any(isinstance(q, Box) for q in questions.values())
        session = await self._get_session()
        started = time.monotonic()
        try:
            async with session.post(
                f"{self._base_url}{SYSTEMONE_PATH}",
                json=payload,
                headers=self._headers(images=images),
                timeout=self._timeout,
            ) as response:
                body = await response.text()
                self._raise_for_status(response, body)
                data = await response.json(content_type=None)
        except aiohttp.ClientError as err:
            # Every HTTP status is raised as a JevError above, so this is only a
            # request that never got an answer.
            raise JevConnectionError(
                f"request to {self._base_url} failed: {err}"
            ) from err
        except TimeoutError as err:
            raise JevConnectionError(
                f"no answer from {self._base_url} within {self._timeout.total}s"
            ) from err

        latency_ms = (time.monotonic() - started) * 1000
        return self._parse(data, latency_ms)

    @staticmethod
    def _raise_for_status(response: aiohttp.ClientResponse, body: str) -> None:
        status = response.status
        if status < 400:
            return
        detail = _api_message(body)
        if status == 401:
            raise JevAuthError(f"the API key was rejected: {detail}", status=status)
        # TypeSafe answered 400 to an unknown model and to an image of the wrong
        # size (measured 2026-10-16). Its docs give 413 for a request over a size
        # limit. 422 is the status this client was first written against.
        if status in (400, 413, 422):
            raise JevValidationError(
                f"the request was rejected as invalid: {detail}", status=status
            )
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            raise JevRateLimitError(
                f"rate limited: {detail}",
                retry_after=float(retry_after) if retry_after else None,
            )
        if status == 529:
            raise JevOverloadedError(
                f"the service is saturated: {detail}", status=status
            )
        raise JevResponseError(f"HTTP {status}: {detail}", status=status)

    @staticmethod
    def _parse(data: Any, latency_ms: float) -> JevResponse:
        if not isinstance(data, Mapping):
            raise JevResponseError(f"expected an object, got {type(data).__name__}")
        raw_answers = data.get("answers")
        if not isinstance(raw_answers, Mapping):
            raise JevResponseError("the reply carries no answers object")
        usage = data.get("usage") or {}
        return JevResponse(
            model=str(data.get("model", "")),
            answers={k: parse_answer(k, v) for k, v in raw_answers.items()},
            usage=Usage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            ),
            latency_ms=latency_ms,
        )

    async def async_close(self) -> None:
        """Close the session, but only the one this client created itself."""
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.async_close()


def _check_references(payload: Mapping[str, Any], assets: Mapping[str, Image]) -> None:
    """Refuse an asset that nothing refers to, before a request is spent on it.

    The API answers 400 to such a request. It looks for references in string values
    only, never in object keys, so this searches the same places.
    """
    text = "\n".join(_strings([payload["state"], payload["questions"]]))
    missing = [ref for ref in assets if not ref.strip() or ref not in text]
    if missing:
        raise ValueError(
            "every asset must be referenced in the state, an instruction or a "
            f"criterion; not found: {missing[:10]}"
        )


def _strings(value: Any) -> list[str]:
    """Every string value in a JSON-shaped structure, keys left out."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [s for item in value.values() for s in _strings(item)]
    if isinstance(value, list | tuple):
        return [s for item in value for s in _strings(item)]
    return []


def _api_message(body: str) -> str:
    """The message out of an error body, or the body itself when it carries none.

    TypeSafe answers {"detail": {"error_type": ..., "message": ...}}, measured on
    2026-10-16 for a 400 and a 401. OpenRouter answers {"error": {"message": ...}},
    measured for a 401 the same day. Anything else, such as a proxy's HTML page or a
    validation list, comes through as it was, cut at 400 characters.
    """
    raw = body.strip()
    try:
        data = json.loads(raw)
    except ValueError:
        return raw[:400]
    if isinstance(data, Mapping):
        for key in ("detail", "error"):
            value = data.get(key)
            if isinstance(value, Mapping):
                value = value.get("message")
            if isinstance(value, str) and value.strip():
                return value.strip()[:400]
    return raw[:400]
