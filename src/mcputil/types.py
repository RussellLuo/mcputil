from __future__ import annotations

import asyncio
from dataclasses import dataclass


CLIENT_TOKEN = "__mcputil_client_token__"


class ProgressToken:
    """A unique token representing a tool progress stream.

    The format is `<CLIENT_TOKEN>/<call_id>`. For example, `__mcputil_client_token__/1234567890`.
    """

    def __init__(self, call_id: str):
        self.call_id = call_id

    @classmethod
    def load(cls, token: str) -> ProgressToken:
        parts = token.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid progress token format: {token}")
        if parts[0] != CLIENT_TOKEN:
            raise ValueError(f"Invalid client token in progress token: {token}")
        return cls(call_id=parts[1])

    @property
    def token(self) -> str:
        return f"{CLIENT_TOKEN}/{self.call_id}"


@dataclass
class ProgressEvent:
    """Parameters for progress notifications."""

    progress: float | None = None
    """
    The progress thus far. This should increase every time progress is made, even if the
    total is unknown.
    """

    total: float | None = None
    """Total number of items to process (or total progress required), if known."""

    message: str | None = None
    """
    Message related to progress. This should provide relevant human readable
    progress information.
    """


class EventBus:
    """A simple event bus for distributing progress events."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def subscribe(self, call_id: str, queue: asyncio.Queue) -> None:
        """Subscribe to a specific call ID's progress events."""
        async with self._lock:
            if call_id not in self._queues:
                self._queues[call_id] = queue

    async def unsubscribe(self, call_id: str) -> None:
        """Unsubscribe from a specific call ID's progress events."""
        async with self._lock:
            if call_id in self._queues:
                del self._queues[call_id]

    async def publish(self, call_id: str, event: ProgressEvent) -> None:
        """Publish a progress event to all subscribers of the call ID."""
        async with self._lock:
            queue = self._queues.get(call_id)
            if queue:
                queue.put_nowait(event)
