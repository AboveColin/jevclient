"""The client against a local server that records what it was sent."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from jevclient import (
    Box,
    BoxAnswer,
    Choice,
    Image,
    JevClient,
    JevRateLimitError,
    JevResponseError,
    JevValidationError,
    Noul,
)

JPEG = b"\xff\xd8\xff\xe0 not a real jpeg, the server never decodes it"


class Recorder:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.body: dict[str, Any] = {}
        self.status = 200
        self.reply: Any = {
            "model": "jev-1.14.0",
            "answers": {"q": {"type": "noul", "noul": 0.9}},
            "usage": {"input_tokens": 300, "output_tokens": 20},
        }

    async def handle(self, request: web.Request) -> web.Response:
        self.headers = dict(request.headers)
        self.body = await request.json()
        if self.status != 200:
            return web.Response(status=self.status, text=str(self.reply))
        return web.json_response(self.reply)


@pytest.fixture
async def server() -> AsyncIterator[tuple[Recorder, str]]:
    recorder = Recorder()
    app = web.Application()
    app.router.add_post("/v1/systemone", recorder.handle)
    test_server = TestServer(app)
    await test_server.start_server()
    try:
        yield recorder, str(test_server.make_url("")).rstrip("/")
    finally:
        await test_server.close()


async def test_a_text_request_carries_no_images_header(server) -> None:
    recorder, url = server
    async with JevClient("key", base_url=url) as jev:
        await jev.ask("state", {"q": Noul("Is it?")})
    assert "TypeSafe-Danger-Zone-Images" not in recorder.headers
    assert "assets" not in recorder.body
    assert recorder.headers["Authorization"] == "Bearer key"


async def test_an_image_goes_in_assets_with_the_header(server) -> None:
    recorder, url = server
    async with JevClient("key", base_url=url) as jev:
        await jev.ask(
            {"photo": "ref-1"},
            {"q": Noul("Is there a parcel in `photo`?")},
            assets={"ref-1": Image(JPEG, "JPG")},
        )
    assert recorder.headers["TypeSafe-Danger-Zone-Images"] == "true"
    assert recorder.body["assets"] == {
        "ref-1": {
            "type": "image",
            "format": "jpg",
            "data_base64": base64.b64encode(JPEG).decode(),
        }
    }


async def test_a_box_question_alone_turns_the_header_on(server) -> None:
    recorder, url = server
    recorder.reply = {
        "model": "jev-1.14.0",
        "answers": {
            "q": {
                "type": "box",
                "box": {"top": 0.19, "bottom": 0.5, "left": 0.59, "right": 0.79},
                "confidence": 0.96,
            }
        },
        "usage": {"input_tokens": 1460, "output_tokens": 20},
    }
    async with JevClient("key", base_url=url) as jev:
        response = await jev.ask("ref-1", {"q": Box("the red square in the image")})
    assert recorder.headers["TypeSafe-Danger-Zone-Images"] == "true"
    assert recorder.body["questions"] == {
        "q": {"type": "box", "instructions": "the red square in the image"}
    }
    answer = response["q"]
    assert isinstance(answer, BoxAnswer)
    assert answer.value == (0.59, 0.19, 0.79, 0.5)
    assert answer.confidence == 0.96


async def test_a_reference_in_an_instruction_or_a_criterion_counts(server) -> None:
    recorder, url = server
    async with JevClient("key", base_url=url) as jev:
        await jev.ask(
            "a hand",
            {
                "same": Noul("Is this the badge photo: ref-badge?"),
                "gesture": Choice(
                    "Which gesture?", {"thumbs_up": "ref-thumb", "none": "No hand"}
                ),
            },
            assets={"ref-badge": Image(JPEG, "jpg"), "ref-thumb": Image(JPEG, "png")},
        )
    assert set(recorder.body["assets"]) == {"ref-badge", "ref-thumb"}


async def test_an_unreferenced_asset_is_refused_before_a_request(server) -> None:
    recorder, url = server
    async with JevClient("key", base_url=url) as jev:
        with pytest.raises(ValueError, match="ref-lost"):
            await jev.ask(
                # A key is not a reference: the API never replaces object keys.
                {"ref-lost": "a key"},
                {"q": Noul("Is it?")},
                assets={"ref-lost": Image(JPEG, "jpg")},
            )
    assert recorder.body == {}


@pytest.mark.parametrize(
    ("data", "fmt", "match"),
    [
        (JPEG, "gif", "png or jpg"),
        (b"", "jpg", "0 bytes"),
        (b"x" * (16 * 1024 * 1024 + 1), "jpg", "at most"),
    ],
)
def test_an_image_the_api_would_refuse_is_refused_here(data, fmt, match) -> None:
    with pytest.raises(ValueError, match=match):
        Image(data, fmt)


@pytest.mark.parametrize("status", [400, 413, 422])
async def test_a_refused_request_is_a_validation_error_with_its_status(
    server, status
) -> None:
    recorder, url = server
    recorder.status = status
    recorder.reply = "Unknown model: jev-nope"
    async with JevClient("key", base_url=url) as jev:
        with pytest.raises(JevValidationError, match="Unknown model") as err:
            await jev.ask("state", {"q": Noul("Is it?")})
    assert err.value.status == status


async def test_other_statuses_keep_their_message_and_carry_the_status(server) -> None:
    recorder, url = server
    recorder.status = 404
    recorder.reply = "Not Found"
    async with JevClient("key", base_url=url) as jev:
        with pytest.raises(JevResponseError, match=r"^HTTP 404: Not Found") as err:
            await jev.ask("state", {"q": Noul("Is it?")})
    assert err.value.status == 404

    recorder.status = 429
    async with JevClient("key", base_url=url) as jev:
        with pytest.raises(JevRateLimitError) as limited:
            await jev.ask("state", {"q": Noul("Is it?")})
    assert limited.value.status == 429
