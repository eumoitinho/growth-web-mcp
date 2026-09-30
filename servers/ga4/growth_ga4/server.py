"""Streamable HTTP entry point for the official Google Analytics MCP server.

Upstream `analytics-mcp` only speaks stdio. This module reuses its low-level
MCP `Server` (tools, schemas, credential handling) unchanged, registers a few
extra read-only Admin tools, and serves everything over stateless Streamable
HTTP so it can run on Cloud Run behind IAM.

Credentials: Application Default Credentials. On Cloud Run that is the
service's runtime service account, which must be granted Viewer on the GA4
properties (Admin > Property access management).
"""

import contextlib
import json
import logging
import os

import uvicorn
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

import analytics_mcp.coordinator as coordinator
from growth_ga4.extra_tools import EXTRA_TOOLS

logger = logging.getLogger("growth_ga4")
MCP_PATH = "/mcp"


def register_extra_tools() -> None:
    """Adds EXTRA_TOOLS to upstream's tool registry.

    Upstream's list_tools/call_tool handlers read the module-level `mcp_tools`
    list and `tool_map` dict, so extending them is enough.
    """
    for fn in EXTRA_TOOLS:
        adk_tool = FunctionTool(fn)
        mcp_tool = adk_to_mcp_tool_type(adk_tool)
        if not mcp_tool.inputSchema:
            mcp_tool.inputSchema = {"type": "object", "properties": {}}
        for prop in mcp_tool.inputSchema.get("properties", {}).values():
            if "anyOf" in prop and prop.get("type") == "null":
                del prop["type"]
        coordinator.sanitize_mcp_schema_properties(mcp_tool.inputSchema)
        coordinator.tool_map[adk_tool.name] = adk_tool
        coordinator.mcp_tools.append(mcp_tool)


register_extra_tools()

session_manager = StreamableHTTPSessionManager(
    app=coordinator.app,
    stateless=True,
    json_response=True,
)


async def _send_json(send, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def app(scope, receive, send):
    """Minimal ASGI router: /mcp -> MCP, /healthz -> ok, rest -> 404."""
    if scope["type"] == "lifespan":
        async with contextlib.AsyncExitStack() as stack:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await stack.enter_async_context(session_manager.run())
                await send({"type": "lifespan.startup.complete"})
            message = await receive()
            if message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
        return

    path = scope.get("path", "").rstrip("/")
    if scope["type"] == "http" and path == MCP_PATH:
        await session_manager.handle_request(scope, receive, send)
    elif scope["type"] == "http" and path == "/healthz":
        await _send_json(send, 200, {"status": "ok", "tools": len(coordinator.mcp_tools)})
    else:
        await _send_json(send, 404, {"error": "not found"})


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        access_log=False,
    )


if __name__ == "__main__":
    main()
