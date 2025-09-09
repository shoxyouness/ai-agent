# src/tools/brave_tools.py
# Brave browser control via Playwright MCP (SSE transport, MCP >= 1.12)

import os
import asyncio
from functools import wraps
from typing import Any, Dict, Optional

from langchain_core.tools import tool
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# ---- Config ----
# Start your server in another terminal and keep it open:
# npx @playwright/mcp@latest --browser=chrome --caps=tabs --port 8931 --executable-path="C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
MCP_SSE_URL = os.environ.get("BRAVE_MCP_SSE_URL", "http://localhost:8931/sse")

# Shared session + the context manager so we can keep the connection open
_session: Optional[ClientSession] = None
_sse_cm = None  # to hold the context manager so it isn't garbage-collected
_lock = asyncio.Lock()


async def _session_ensure() -> ClientSession:
    """Create (or return) a shared MCP session connected to the Playwright MCP server over SSE."""
    global _session, _sse_cm
    async with _lock:
        if _session is not None:
            return _session

        # Manually enter the async context and DO NOT exit it
        _sse_cm = sse_client(MCP_SSE_URL)
        read_stream, write_stream = await _sse_cm.__aenter__()  # keep open for app lifetime
        _session = ClientSession(read_stream, write_stream)
        await _session.initialize()
        return _session


def _syncify(fn):
    """Wrap an async tool so it can be called synchronously by LangChain."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


async def _call(name: str, args: Dict[str, Any]) -> Any:
    """Call an MCP tool and return text content if present; otherwise the raw payload."""
    s = await _session_ensure()
    res = await s.call_tool(name=name, arguments=args)
    parts = res.content or []
    texts = [
        getattr(p, "text", "")
        for p in parts
        if getattr(p, "type", "") == "text" and hasattr(p, "text")
    ]
    return "\n".join([t for t in texts if t]) if texts else res.model_dump()


# -------------------- Tools --------------------

@tool("browser_navigate")
@_syncify
async def browser_navigate(url: str):
    """Navigate the current tab to the given URL."""
    return await _call("browser_navigate", {"url": url})


@tool("browser_snapshot")
@_syncify
async def browser_snapshot():
    """Return a semantic accessibility snapshot of the current page (roles, names, and element refs)."""
    return await _call("browser_snapshot", {})


@tool("browser_click")
@_syncify
async def browser_click(element: str, ref: str, doubleClick: bool = False, button: Optional[str] = None):
    """Click an element identified by (element, ref) from a prior browser_snapshot()."""
    args: Dict[str, Any] = {"element": element, "ref": ref, "doubleClick": doubleClick}
    if button:
        args["button"] = button
    return await _call("browser_click", args)


@tool("browser_type")
@_syncify
async def browser_type(element: str, ref: str, text: str, submit: bool = False):
    """Type text into an input identified by (element, ref); set submit=True to press Enter afterward."""
    return await _call("browser_type", {"element": element, "ref": ref, "text": text, "submit": submit})


@tool("browser_evaluate")
@_syncify
async def browser_evaluate(function: str, element: Optional[str] = None, ref: Optional[str] = None):
    """Evaluate a small JavaScript function in the page context; optionally scope to an element via (element, ref)."""
    args: Dict[str, Any] = {"function": function}
    if element:
        args["element"] = element
    if ref:
        args["ref"] = ref
    return await _call("browser_evaluate", args)


@tool("browser_take_screenshot")
@_syncify
async def browser_take_screenshot(filename: Optional[str] = None, type: Optional[str] = None):
    """Capture a screenshot of the current page. Optionally specify filename and image type (png|jpeg)."""
    args: Dict[str, Any] = {}
    if filename:
        args["filename"] = filename
    if type:
        args["type"] = type
    return await _call("browser_take_screenshot", args)


@tool("browser_navigate_back")
@_syncify
async def browser_navigate_back():
    """Navigate back in the current tab's history."""
    return await _call("browser_navigate_back", {})


@tool("browser_navigate_forward")
@_syncify
async def browser_navigate_forward():
    """Navigate forward in the current tab's history."""
    return await _call("browser_navigate_forward", {})


@tool("browser_tab_new")
@_syncify
async def browser_tab_new(url: Optional[str] = None):
    """Open a new tab, optionally with a starting URL. Requires the server to run with --caps=tabs."""
    args: Dict[str, Any] = {}
    if url:
        args["url"] = url
    return await _call("browser_tab_new", args)


@tool("browser_tab_select")
@_syncify
async def browser_tab_select(index: int):
    """Select/switch to a tab by zero-based index. Requires the server to run with --caps=tabs."""
    return await _call("browser_tab_select", {"index": index})
