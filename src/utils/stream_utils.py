import asyncio
import contextvars
from typing import Any, Dict, Optional
from concurrent.futures import Future

# The global context variable that holds the current stream emitter
_emitter_ctx: contextvars.ContextVar[Optional['StreamEmitter']] = contextvars.ContextVar('stream_emitter', default=None)

class StreamEmitter:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.loop = asyncio.get_running_loop()
        self._pending_futures: list[Future] = []

    def emit(self, event: Dict[str, Any]) -> Future:
        """Thread-safe emit. Returns a Future that resolves when the event is queued."""
        # Thread-safe since agents might be running in synchronous threads or ThreadPoolExecutor
        fut = asyncio.run_coroutine_threadsafe(self.queue.put(event), self.loop)
        self._pending_futures.append(fut)
        return fut

    def emit_tool_call(self, name: str, args: Any):
        self.emit({"type": "tool_call", "name": name, "args": args})

    def emit_tool_result(self, name: str, result: str):
        preview = str(result)[:300] + ("..." if len(str(result)) > 300 else "")
        self.emit({"type": "tool_result", "name": name, "preview": preview})

    def emit_agent_start(self, agent_name: str):
        self.emit({"type": "agent_start", "agent": agent_name})

    def emit_agent_tool_call(self, agent_name: str, name: str, args: Any):
        self.emit({"type": "agent_tool_call", "agent": agent_name, "name": name, "args": args})

    def emit_agent_tool_result(self, agent_name: str, name: str, result: str):
        preview = str(result)[:300] + ("..." if len(str(result)) > 300 else "")
        self.emit({"type": "agent_tool_result", "agent": agent_name, "name": name, "preview": preview})

    def emit_agent_done(self, agent_name: str, summary: str):
        self.emit({"type": "agent_done", "agent": agent_name, "summary": summary})

    async def flush(self, timeout: float = 2.0):
        """Wait for all pending emissions to complete. Call before sending 'done' event."""
        if not self._pending_futures:
            return
        # Wait for all futures with timeout
        done, pending = await asyncio.wait(
            [asyncio.wrap_future(f) for f in self._pending_futures],
            timeout=timeout,
            return_when=asyncio.ALL_COMPLETED
        )
        # Clear completed futures, keep any that timed out (shouldn't happen with unbounded queue)
        self._pending_futures = [f for f in self._pending_futures if f in pending]

def get_emitter() -> Optional[StreamEmitter]:
    return _emitter_ctx.get()

def set_emitter(emitter: StreamEmitter):
    _emitter_ctx.set(emitter)
