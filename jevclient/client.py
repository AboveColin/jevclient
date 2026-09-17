"""Async client for the TypeSafe System One endpoint."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any, Self

import aiohttp

from .const import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
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
from .models import JevResponse, Question, Usage, parse_answer

StateType = str | Mapping[str, Any] | list[Any]


class JevClient:
    """One client per API key.

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
    ) -> JevResponse:
        """Evaluate every question against one state and return typed answers.

        The keys of `questions` come back as the keys of `answers`. They are not
        sent to the model and play no part in inference, so name them for your code.
        """
        if not questions:
            raise ValueError("ask() needs at least one question")

        payload = {
            "state": state,
            "model": model or self._model,
            "questions": {key: q.as_payload() for key, q in questions.items()},
        }
        session = await self._get_session()
        started = time.monotonic()
        try:
            async with session.post(
                f"{self._base_url}{SYSTEMONE_PATH}",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            ) as response:
                body = await response.text()
                self._raise_for_status(response, body)
                data = await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise JevConnectionError(f"request to {self._base_url} failed: {err}") from err
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
        detail = body.strip()[:400]
        if status == 401:
            raise JevAuthError(f"the API key was rejected: {detail}")
        if status == 422:
            raise JevValidationError(f"the request was rejected as invalid: {detail}")
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            raise JevRateLimitError(
                f"rate limited: {detail}",
                retry_after=float(retry_after) if retry_after else None,
            )
        if status == 529:
            raise JevOverloadedError(f"the service is saturated: {detail}")
        raise JevResponseError(f"HTTP {status}: {detail}")

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
