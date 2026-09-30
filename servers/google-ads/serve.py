"""Cloud Run entry point for the official Google Ads MCP server.

Upstream `google-ads-mcp` has two modes:
  * stdio + Application Default Credentials (no OAuth env vars), and
  * Streamable HTTP + FastMCP Google OAuth proxy (per-user login, tokens in
    Firestore/Redis) when GOOGLE_ADS_MCP_OAUTH_CLIENT_ID/SECRET are set.

This wrapper adds a third mode used by this repo: Streamable HTTP + ADC, with
access control delegated to Cloud Run IAM (roles/run.invoker). The runtime
service account is granted read access directly in Google Ads (service
account direct access, no domain-wide delegation needed).

Set ADS_MCP_MODE=oauth to fall back to upstream's OAuth proxy behaviour.
"""

import os

from starlette.requests import Request
from starlette.responses import JSONResponse

from ads_mcp import server as upstream_server
from ads_mcp.coordinator import mcp


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def main() -> None:
    if os.environ.get("ADS_MCP_MODE", "iam") == "oauth":
        upstream_server.run_server()
        return

    mcp.run(
        transport="streamable-http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        path="/mcp",
        stateless_http=True,
        json_response=True,
        show_banner=False,
        uvicorn_config={"access_log": False},
    )


if __name__ == "__main__":
    main()
