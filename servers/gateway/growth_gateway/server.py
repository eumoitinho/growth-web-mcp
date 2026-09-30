"""Public MCP gateway for claude.ai custom connectors.

The read servers (ga4, google-ads, gtm, hubspot, meta, site-browser) stay
private on Cloud Run behind IAM. claude.ai cannot present a Google ID token, it
speaks MCP OAuth (dynamic client registration + PKCE). This gateway is the one
public URL: it runs that OAuth flow against Google Sign-In, accepts only
verified accounts in configured domains, and forwards every call to the private servers
with its own service account's ID token (and to WordPress with the Basic
credential from Secret Manager). Write servers are never exposed here.

Layout of the tools the connector shows:
  ga4_*, ads_*, meta_*, site_*, wp_*   namespaced here
  gtm_*, hubspot-*                     already prefixed upstream, kept as is
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx2
from cryptography.fernet import Fernet
from fastmcp import FastMCP
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.providers.proxy import ProxyClient, ProxyProvider
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger("growth_gateway")

# (namespace, env var with the upstream /mcp URL). An empty namespace keeps the
# upstream names, which already carry a prefix (gtm_*, hubspot-*).
UPSTREAMS = [
    ("ga4", "GROWTH_MCP_GA4_URL"),
    ("ads", "GROWTH_MCP_GOOGLE_ADS_URL"),
    ("", "GROWTH_MCP_GTM_URL"),
    ("", "GROWTH_MCP_HUBSPOT_URL"),
    ("meta", "GROWTH_MCP_META_URL"),
    ("site", "GROWTH_MCP_SITE_BROWSER_URL"),
]
# Browser sessions are stateful (the page you navigated is the page you
# inspect), so each person keeps one upstream session; the rest are stateless.
STATEFUL = {"site"}
STATEFUL_IDLE_SECONDS = 14 * 60  # site-browser drops sessions after 15 min

CLAUDE_CALLBACKS = [
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
]


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        sys.exit(f"{name} is not set")
    return value


# --- identity: who may use the connector ------------------------------------

class DomainVerifier(TokenVerifier):
    """Wraps the Google verifier: valid token AND verified e-mail in the domain."""

    def __init__(self, inner: TokenVerifier, domains: set[str]):
        super().__init__(required_scopes=inner.required_scopes)
        self._inner = inner
        self._domains = domains

    async def verify_token(self, token: str) -> AccessToken | None:
        verified = await self._inner.verify_token(token)
        if verified is None:
            return None
        email = str(verified.claims.get("email") or "").lower()
        email_ok = verified.claims.get("email_verified") in (True, "true")
        if not email_ok or email.rpartition("@")[2] not in self._domains:
            log.warning(json.dumps({"event": "auth_denied", "email": email or None}))
            return None
        return verified


class DomainRestrictedGoogleProvider(GoogleProvider):
    def __init__(self, *, allowed_domains: set[str], **kwargs):
        super().__init__(**kwargs)
        self._token_validator = DomainVerifier(self._token_validator, allowed_domains)


def _client_storage():
    """OAuth registrations and tokens must survive restarts and scale-out,
    otherwise every deploy logs the whole team out. Firestore, encrypted."""
    if os.environ.get("GATEWAY_STORAGE", "firestore") == "memory":
        return None  # local testing: FastMCP's encrypted file store
    from key_value.aio.stores.firestore import FirestoreStore
    from key_value.aio.stores.firestore.store import FirestoreV1KeySanitizationStrategy

    # claude.ai registers with a URL as client_id (CIMD); Firestore document
    # IDs cannot contain "/", so keys and collections are sanitized (+ hash).
    store = FirestoreStore(
        project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        database=os.environ.get("GATEWAY_FIRESTORE_DATABASE", "(default)"),
        default_collection="mcp-gateway-oauth",
        key_sanitization_strategy=FirestoreV1KeySanitizationStrategy(),
        collection_sanitization_strategy=FirestoreV1KeySanitizationStrategy(),
    )
    return FernetEncryptionWrapper(
        key_value=store,
        fernet=Fernet(_env("GATEWAY_STORAGE_KEY").encode()),
        raise_on_decryption_error=False,  # a rotated key just means re-login
    )


def build_auth() -> GoogleProvider:
    return DomainRestrictedGoogleProvider(
        allowed_domains={d.strip().lower() for d in _env("GATEWAY_ALLOWED_DOMAINS").split(",")},
        client_id=_env("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=_env("GOOGLE_OAUTH_CLIENT_SECRET"),
        base_url=_env("GATEWAY_BASE_URL"),
        required_scopes=["openid", "email"],
        allowed_client_redirect_uris=os.environ.get("GATEWAY_CLIENT_REDIRECTS", ",".join(CLAUDE_CALLBACKS)).split(","),
        client_storage=_client_storage(),
        jwt_signing_key=_env("GATEWAY_JWT_KEY"),
        require_authorization_consent="remember",
        # Only a hint for the account chooser; DomainVerifier enforces it.
        extra_authorize_params={"hd": _env("GATEWAY_ALLOWED_DOMAINS").split(",")[0]},
    )


def _current_email() -> str:
    token = get_access_token()
    return str((token.claims.get("email") if token else None) or "anonymous")


# --- upstream credentials ----------------------------------------------------

class IdTokenAuth(httpx2.Auth):
    """Cloud Run service-to-service auth: an ID token for the upstream URL,
    minted by the gateway's service account and cached until near expiry."""

    def __init__(self, url: str):
        self._audience = url.removesuffix("/mcp")
        self._token = ""
        self._expires = 0.0

    def _fresh(self) -> str:
        if time.time() < self._expires - 300:
            return self._token
        if os.environ.get("GATEWAY_UPSTREAM_AUTH") == "gcloud":
            # Local testing with a person's gcloud login (user ID tokens carry
            # a fixed audience, which Cloud Run accepts for run.invoker users).
            self._token = subprocess.check_output(
                ["gcloud", "auth", "print-identity-token"], text=True).strip()
        else:
            import google.auth.transport.requests
            import google.oauth2.id_token

            self._token = google.oauth2.id_token.fetch_id_token(
                google.auth.transport.requests.Request(), self._audience)
        self._expires = time.time() + 3600
        return self._token

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self._fresh()}"
        yield request


def _stateless_factory(url: str, auth: httpx2.Auth | None = None, headers: dict | None = None):
    def factory() -> Client:
        return ProxyClient(StreamableHttpTransport(url, auth=auth, headers=headers))
    return factory


def _per_user_factory(url: str, auth: httpx2.Auth):
    """One long-lived upstream session per person (site-browser)."""
    sessions: dict[str, tuple[Client, float]] = {}

    async def factory() -> Client:
        email = _current_email()
        now = time.time()
        for key, (client, last) in list(sessions.items()):
            if now - last > STATEFUL_IDLE_SECONDS:
                sessions.pop(key, None)
                if client.is_connected():
                    await client.__aexit__(None, None, None)
        client, _ = sessions.get(email, (None, 0.0))
        if client is None or not client.is_connected():
            client = ProxyClient(StreamableHttpTransport(url, auth=auth))
            await client.__aenter__()
        sessions[email] = (client, now)
        return client

    return factory


# --- audit log -----------------------------------------------------------------

class AuditLog(Middleware):
    """One structured line per tool call (Cloud Logging parses JSON stdout)."""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        started = time.monotonic()
        entry = {"event": "tool_call", "email": _current_email(), "tool": context.message.name}
        try:
            result = await call_next(context)
            entry["ok"] = not bool(getattr(result, "isError", False))
            return result
        except Exception as exc:
            entry.update(ok=False, error=type(exc).__name__)
            raise
        finally:
            entry["ms"] = int((time.monotonic() - started) * 1000)
            print(json.dumps(entry), flush=True)


# --- server ----------------------------------------------------------------------

def build_server() -> FastMCP:
    instructions = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")
    mcp = FastMCP("Growth MCP", instructions=instructions, auth=build_auth())
    mcp.add_middleware(AuditLog())

    for namespace, env_name in UPSTREAMS:
        url = os.environ.get(env_name)
        if not url:
            log.warning("%s not set; skipping", env_name)
            continue
        auth = IdTokenAuth(url)
        factory = _per_user_factory(url, auth) if namespace in STATEFUL else _stateless_factory(url, auth)
        mcp.add_provider(ProxyProvider(factory), namespace=namespace)

    wp_url, wp_basic = os.environ.get("WP_MCP_URL"), os.environ.get("WP_MCP_BASIC_AUTH")
    if wp_url and wp_basic:
        mcp.add_provider(
            ProxyProvider(_stateless_factory(wp_url, headers={"Authorization": f"Basic {wp_basic}"})),
            namespace="wp",
        )

    # Cloud Run reserves paths ending in "z" (/healthz answers 404 at the frontend).
    @mcp.custom_route("/health", methods=["GET"])
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    return mcp


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    build_server().run(
        transport="http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        path="/mcp",
        # No front-session state to lose on redeploy; site-browser sessions are
        # keyed by person instead (see _per_user_factory).
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
