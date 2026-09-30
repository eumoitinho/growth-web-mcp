#!/usr/bin/env python3
"""Lists the tools exposed by an MCP server over Streamable HTTP.

Usage:
  python scripts/smoke_test.py http://localhost:8080/mcp
  python scripts/smoke_test.py https://growth-mcp-ga4-xxxx.a.run.app/mcp --id-token
  python scripts/smoke_test.py URL --call get_account_summaries '{}'

--id-token adds `Authorization: Bearer $(gcloud auth print-identity-token)`,
which Cloud Run services deployed with IAM auth require.

Requires: pip install "mcp>=1.24" (1.x and 2.x supported)
"""

import argparse
import asyncio
import json
import subprocess

from contextlib import asynccontextmanager

from mcp import ClientSession

try:  # mcp >= 2
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    @asynccontextmanager
    async def connect(url, headers):
        async with create_mcp_http_client(headers=headers) as http:
            async with streamable_http_client(url, http_client=http) as streams:
                yield streams[0], streams[1]

except ImportError:  # mcp 1.x
    from mcp.client.streamable_http import streamablehttp_client

    @asynccontextmanager
    async def connect(url, headers):
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            yield read, write


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--id-token", action="store_true")
    parser.add_argument("--call", nargs=2, metavar=("TOOL", "JSON_ARGS"))
    args = parser.parse_args()

    headers = {}
    if args.id_token:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-identity-token"], text=True
        ).strip()
        headers["Authorization"] = f"Bearer {token}"

    async with connect(args.url, headers) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            info = getattr(init, "server_info", None) or init.serverInfo  # 2.x / 1.x
            print(f"server: {info.name} {info.version}")
            tools = (await session.list_tools()).tools
            print(f"{len(tools)} tools:")
            for tool in tools:
                first_line = (tool.description or "").strip().splitlines()[0:1]
                print(f"  - {tool.name}: {first_line[0][:90] if first_line else ''}")
            if args.call:
                name, raw = args.call
                result = await session.call_tool(name, json.loads(raw))
                if result.isError:
                    raise RuntimeError(f"MCP tool {name!r} returned isError=true")
                for part in result.content:
                    print(getattr(part, "text", part))


if __name__ == "__main__":
    asyncio.run(main())
