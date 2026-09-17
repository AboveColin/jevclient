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

## Three question types

| Type | Ask it | You get back |
|---|---|---|
| `Noul` | a yes/no question | `noul`, the probability the answer is yes |
| `Choice` | pick one of your options | `choice`, `probabilities`, `confidence` |
| `Score` | rate against ordered levels | `score`, `legend`, `probabilities`, `confidence` |

A `Noul` carries no confidence, because the probability is the whole answer.

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

## Install

```
pip install jevclient
```

Requires Python 3.12 and aiohttp. Pass your own `aiohttp.ClientSession` if you have
one, and the client will use it and leave closing it to you.

## Errors

`JevAuthError` (401), `JevValidationError` (422), `JevRateLimitError` (429, carries
`retry_after`), `JevOverloadedError` (529) and `JevConnectionError`, all deriving
from `JevError`. There is no internal retry loop, so the caller decides the policy.

A `Choice` with fewer than two options and a `Score` with fewer than two levels are
refused locally, before a request is spent on a 422.

## Not affiliated with TypeSafe

This is an independent client. See the [TypeSafe docs](https://docs.typesafe.ai) for
the API itself.
