"""
Server-Sent Events (SSE) utilities for streaming responses
"""
import json
from typing import AsyncGenerator, Callable, Any
from app.dtos import StreamEvent


def format_sse(event: StreamEvent, event_type: str = "message") -> str:
    """
    Format StreamEvent as SSE message

    SSE format:
    event: <type>
    data: <json>

    Args:
        event: StreamEvent to format
        event_type: SSE event type (default: "message")

    Returns:
        Formatted SSE string
    """
    data = event.model_dump_json()
    return f"event: {event_type}\ndata: {data}\n\n"


async def stream_with_heartbeat(
    generator: AsyncGenerator[StreamEvent, None],
    heartbeat_interval: int = 15
) -> AsyncGenerator[str, None]:
    """
    Wrap event generator with heartbeat comments

    Sends SSE comment every N seconds to keep connection alive

    Args:
        generator: Async generator of StreamEvents
        heartbeat_interval: Seconds between heartbeats

    Yields:
        SSE formatted strings
    """
    import asyncio

    last_heartbeat = asyncio.get_event_loop().time()

    async for event in generator:
        # Send event
        yield format_sse(event, event_type=event.stage)

        # Check if heartbeat needed
        now = asyncio.get_event_loop().time()
        if now - last_heartbeat > heartbeat_interval:
            yield ": heartbeat\n\n"
            last_heartbeat = now

    # Send final done marker
    yield "event: done\ndata: {}\n\n"


class EventEmitter:
    """
    Helper to emit events from synchronous code

    Usage:
        emitter = EventEmitter()

        async def stream():
            async for event in emitter.events():
                yield event

        # In sync code:
        emitter.emit(StreamEvent(stage="start", progress=0))
        emitter.emit(StreamEvent(stage="done", progress=100))
        emitter.close()
    """

    def __init__(self):
        self._queue: list[StreamEvent] = []
        self._closed = False

    def emit(self, event: StreamEvent) -> None:
        """Add event to queue"""
        if not self._closed:
            self._queue.append(event)

    def close(self) -> None:
        """Mark emitter as closed"""
        self._closed = True

    async def events(self) -> AsyncGenerator[StreamEvent, None]:
        """
        Async generator that yields queued events

        Polls queue until closed
        """
        import asyncio

        while not self._closed or self._queue:
            if self._queue:
                yield self._queue.pop(0)
            else:
                await asyncio.sleep(0.01)  # Small delay to prevent tight loop
