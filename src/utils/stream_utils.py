import asyncio
import contextvars
from typing import Any, Dict, Optional

# The global context variable that holds the current stream emitter
_emitter_ctx: contextvars.ContextVar[Optional['StreamEmitter']] = contextvars.ContextVar('stream_emitter', default=None)

class StreamEmitter:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.loop = asyncio.get_running_loop()

    def emit(self, event: Dict[str, Any]):
        # Thread-safe since agents might be running in synchronous threads or ThreadPoolExecutor
        asyncio.run_coroutine_threadsafe(self.queue.put(event), self.loop)

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

def get_emitter() -> Optional[StreamEmitter]:
    return _emitter_ctx.get()

def set_emitter(emitter: StreamEmitter):
    _emitter_ctx.set(emitter)
