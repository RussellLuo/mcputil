import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from typing_extensions import TypeAlias

import jsonschema
from mcp import ClientSession
import mcp.types as types

from .types import ProgressToken, ProgressEvent, EventBus
from .func import gen_anno_and_sig


@dataclass
class OutputEvent:
    """An output event emitted after a tool has completed execution."""

    output: Any


@dataclass
class ExceptionEvent:
    """An exception event emitted if a tool fails during execution."""

    exc: Exception


Event: TypeAlias = ProgressEvent | OutputEvent


@dataclass
class Result:
    """The result of a tool execution including its output and a way to track progress."""

    _task: asyncio.Task = field(repr=False)
    _queue: asyncio.Queue[Event | ExceptionEvent] = field(repr=False)
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    async def events(self) -> AsyncIterator[Event]:
        """Stream progress events for this result."""
        while True:
            if self._cancel_event.is_set():
                break

            event = await self._queue.get()
            self._queue.task_done()

            if isinstance(event, ProgressEvent):
                yield event
            elif isinstance(event, OutputEvent):
                yield event
                break
            elif isinstance(event, ExceptionEvent):
                raise event.exc

    def cancel(self) -> None:
        """Cancel the task associated with this result."""
        self._task.cancel()

        # Clear the queue to prevent processing stale events.
        while not self._queue.empty():
            self._queue.get_nowait()


@dataclass(kw_only=True)
class Tool:
    """A tool that can be executed on an MCP server."""

    name: str
    description: str = ""
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None

    _client_session: ClientSession = field(repr=False)
    _event_bus: EventBus = field(repr=False)

    def __post_init__(self):
        # Set the name and docstring of the instance to match the tool's metadata.
        self.__name__ = self.name
        self.__doc__ = self.description

        # Generate and set the __annotations__ and __signature__ attributes based on input/output schemas.
        # This enables proper type hints and parameter documentation when the tool is called.
        self.__annotations__, self.__signature__ = gen_anno_and_sig(
            self.input_schema.get("properties", {}),
            (
                self.output_schema.get("properties", {}).get("result")
                if self.output_schema
                else None
            ),
        )

    async def __call__(self, **kwargs) -> Any:
        result: Result = await self.call(call_id=None, **kwargs)
        async for event in result.events():
            if isinstance(event, OutputEvent):
                return event.output
            elif isinstance(event, ExceptionEvent):
                raise event.exc

    async def call(self, call_id: str | None = None, **kwargs) -> Result:
        """Call the tool with a specific call ID, which can be used to track progress."""

        async def f(**kwargs) -> Any:
            # Validate the input against the schema
            jsonschema.validate(instance=kwargs, schema=self.input_schema)

            # Actually call the tool.
            meta = None
            if call_id is not None:
                meta = dict(progressToken=ProgressToken(call_id).token)

            result = await self._client_session.call_tool(
                self.name,
                arguments=kwargs,
                meta=meta,
            )
            if not result.content:
                return ""
            content = result.content[0]

            if result.isError:
                raise ValueError(content.text)

            match content:
                case types.TextContent():
                    return content.text
                case types.ImageContent():
                    return content.data
                case _:  # types.EmbeddedResource() or other types
                    return ""

        queue: asyncio.Queue = asyncio.Queue()

        async def wrapper(**kwargs) -> Any:
            if call_id is not None:
                # Subscribe to progress updates.
                await self._event_bus.subscribe(call_id, queue)
            try:
                output = await f(**kwargs)
                queue.put_nowait(OutputEvent(output=output))
                return output
            except Exception as exc:
                queue.put_nowait(ExceptionEvent(exc=exc))
            finally:
                if call_id is not None:
                    # Unsubscribe from progress updates.
                    await self._event_bus.unsubscribe(call_id)

        task: asyncio.Task = asyncio.create_task(wrapper(**kwargs))
        result = Result(_task=task, _queue=queue)
        return result
