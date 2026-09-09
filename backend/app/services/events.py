"""In-process pub/sub so the admin panel can live-refresh via SSE (see app/api/routes/events.py).

Single-instance only — fine for one clinic's deployment, no cross-process broker needed.
"""

import asyncio

_subscribers: set[asyncio.Queue[None]] = set()


def subscribe() -> asyncio.Queue[None]:
    queue: asyncio.Queue[None] = asyncio.Queue()
    _subscribers.add(queue)
    return queue


def unsubscribe(queue: asyncio.Queue[None]) -> None:
    _subscribers.discard(queue)


def broadcast() -> None:
    for queue in _subscribers:
        queue.put_nowait(None)
