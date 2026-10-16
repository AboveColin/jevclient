# jevclient

Async Python client for [TypeSafe](https://typesafe.ai) Jev, the System One decision
model. Jev answers typed questions about a state and returns values, so there is no
text to parse.

```python
import asyncio
from jevclient import JevClient, Noul, Choice, Score

async def main():
    async with JevClient("your-api-key") as jev:
        answers = await jev.ask(
            "The front door has been unlocked for 40 minutes and nobody is home.",
            {
                "warn": Noul("Should someone be warned about this?"),
                "area": Choice("Which area is this about?",
                               {"security": "Doors, locks, alarms",
                                "climate": "Heating and ventilation"}),
                "urgency": Score("How urgent is it?",
                                 ["Ignore", "Today", "Right now"]),
            },
        )
    print(answers["warn"].noul)          # 0.94
    print(answers["area"].choice)        # "security"
    print(answers["area"].probabilities) # {"security": 0.97, "climate": 0.03}
    print(answers["urgency"].score)      # 1.8, between "Today" and "Right now"

asyncio.run(main())
```

## Four question types

| Type | Ask it | You get back |
|---|---|---|
| `Noul` | a yes/no question | `noul`, the probability the answer is yes |
| `Choice` | pick one of your options | `choice`, `probabilities`, `confidence` |
| `Score` | rate against ordered levels | `score`, `legend`, `probabilities`, `confidence` |
| `Box` | where something is in an image | `top`, `bottom`, `left`, `right`, `confidence` |

A `Noul` carries no confidence, because the probability is the whole answer.

## Images

Pass images in `assets`, keyed by a reference string, and write the reference where
the image belongs: in the state, an instruction or a criterion.

```python
import uuid
from jevclient import Box, Image, JevClient, Noul

door = str(uuid.uuid4())
async with JevClient("your-api-key", model="jev-1.14.0") as jev:
    answers = await jev.ask(
        {"door": door},
        {
            "parcel": Noul("Is there a parcel in `door`?"),
            "where": Box("the parcel in `door`"),
        },
        assets={door: Image(open("door.jpg", "rb").read(), "jpg")},
    )
print(answers["parcel"].noul)   # 0.93
print(answers["where"].value)   # (0.59, 0.19, 0.79, 0.5), left top right bottom
```

- The client sends the `TypeSafe-Danger-Zone-Images: true` header on a request with
  an image or a `Box`, and on no other.
- `Box` needs Jev 1.14 (`jev-1.14.0` or `jev-preview`). On `jev-1.13.0` the API
  answers 400. Images work on both.
- An asset no string refers to is refused locally. The API would answer 400.
- Resize first. The API rejects a side under 280 or over 1568 pixels instead of
  scaling it: a 1920 x 1080 frame comes back 400.

An image is billed as input tokens. Measured on 2026-10-16 against `jev-1.14.0`, the
image part of a request was `2 x ceil(width / 28) x ceil(height / 28)` tokens at
every size tried:

| image | tokens for the image |
|---|---|
| 280 x 280 | 200 |
| 300 x 301 | 242 |
| 784 x 588 | 1,176 |
| 1000 x 750 | 1,944 |
| 1568 x 1176 | 4,704 |
| 1568 x 1568 | 6,272 |

Each place a reference appears adds the image again, so put an image several
questions use in the state once.

## What one call costs

Every question in a call is evaluated in isolation against the same state, and the
API answers them in parallel. Measured from the Netherlands on 2026-09-17:

| questions | input tokens | latency |
|---|---|---|
| 3 | 521 | 712 ms |
| 25 | 1,242 | 690 ms |
| 100 | 4,017 | 714 ms |
| 400 | 15,417 | 1,336 ms |

Two things follow. Batching questions into one call is nearly free in time, so ask
everything you want to know at once. It is not free in money: question text is
billed as input tokens, roughly 38 for a short question, and output is billed at
zero.

Those figures are first calls on a cold connection. Over 16 calls from the same
place, a warm connection answered in 250 to 580 ms.

A choice takes 2 to 255 options and a score takes 2 to 10 levels. Both are checked
locally, so a mistake costs no request.

## Install

```
pip install jevclient
```

Requires Python 3.12 and aiohttp. Pass your own `aiohttp.ClientSession` if you have
one, and the client will use it and leave closing it to you.

## Another endpoint

`base_url` points the client at something other than `https://api.typesafe.ai`, and
`model` names the model to ask for. The client appends `/v1/systemone` to the base
URL, so a path in it is kept as a prefix.

An empty `api_key` sends no Authorization header, for an endpoint that asks for no
credential:

```python
JevClient("", base_url="http://gateway.local:8093", model="systemone-small")
```

## Errors

`JevAuthError` (401), `JevValidationError` (400, 413, 422), `JevRateLimitError`
(429, carries `retry_after`), `JevOverloadedError` (529) and `JevConnectionError`,
all deriving from `JevError`. An error from an HTTP answer carries its `status`.
There is no internal retry loop, so the caller decides the policy.

A `Choice` with fewer than two options, a `Score` with fewer than two levels, and an
image that is not PNG or JPEG, is empty or is over 16 MiB are refused locally,
before a request is spent on them.

## Not affiliated with TypeSafe

This is an independent client. See the [TypeSafe docs](https://docs.typesafe.ai) for
the API itself.

## Supporting the project

This project is free and stays free. If it is useful to you, you can support its
development through [GitHub Sponsors](https://github.com/sponsors/AboveColin).
Sponsorship is voluntary and unlocks nothing: every feature, fix and security
update ships in the public release.
