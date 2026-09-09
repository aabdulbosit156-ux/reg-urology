import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentPrincipal, get_principal_for_sse, require_bot_secret
from app.services.events import broadcast, subscribe, unsubscribe

router = APIRouter(prefix="/events", tags=["events"])

KEEPALIVE_SECONDS = 25


@router.post("/broadcast", status_code=204, dependencies=[Depends(require_bot_secret)])
async def trigger_broadcast() -> None:
    # Lets the bot process (a separate process/container from this web process) wake up
    # connected admin-panel SSE clients after it writes patients/analyses on its own.
    broadcast()


@router.get("")
async def stream_events(_: CurrentPrincipal = Depends(get_principal_for_sse)) -> StreamingResponse:
    queue = subscribe()

    async def generator() -> AsyncIterator[str]:
        try:
            while True:
                try:
                    await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                    yield "event: update\ndata: {}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
