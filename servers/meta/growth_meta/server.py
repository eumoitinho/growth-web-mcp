"""Read-only Meta (Facebook/Instagram) Ads MCP server for Cloud Run.

Why this exists next to Meta's official hosted MCP (https://mcp.facebook.com/ads):
the official server authenticates each person with Meta Business OAuth, which
suits humans in an MCP client, and it can write (campaigns land PAUSED). The
unattended agent needs a stable identity that can only read, so this server
calls the Graph Marketing API with a *system user* token (Secret Manager) and
exposes read tools only, focused on inbound tracking:

  * insights (spend, clicks, leads by campaign/ad set/ad),
  * ad destinations and url_tags (UTMs missing on Meta ads is why Meta traffic
    shows up as Direct/Referral in GA4),
  * pixel / dataset stats by event, host and source (browser vs CAPI; pixel
    firing on LPs, subdomains or staging),
  * Lead Ads forms (leads that never touch the site but reach HubSpot).

Write access is delegated to Meta's official MCP (see docs/write-access.md).
"""

import os
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v26.0")
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
MAX_PAGES = 10

mcp = FastMCP(
    "growth-meta-mcp",
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "8080")),
    stateless_http=True,
    json_response=True,
)


class MetaError(RuntimeError):
    pass


def _token() -> str:
    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise MetaError("META_ACCESS_TOKEN is not set (system user token from Secret Manager).")
    return token


async def _get(path: str, params: dict[str, Any] | None = None, token: str | None = None,
               max_pages: int = 1) -> Any:
    """GET a Graph API edge, following `paging.next` up to max_pages."""
    query = {k: v for k, v in (params or {}).items() if v is not None}
    # Token in the header, never in the URL: keeps it out of logs, exceptions
    # and the `paging.next` links Graph returns.
    headers = {"Authorization": f"Bearer {token or _token()}"}
    url: str | None = f"{GRAPH_URL}/{path.lstrip('/')}"
    rows: list[Any] = []
    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        for _ in range(max_pages):
            response = await client.get(url, params=query)
            body = response.json()
            if response.status_code >= 400 or "error" in body:
                error = body.get("error", {})
                raise MetaError(
                    f"Graph API {response.status_code}: {error.get('message', body)} "
                    f"(code {error.get('code')}, subcode {error.get('error_subcode')})"
                )
            if "data" not in body:
                return body
            rows.extend(body["data"])
            url = body.get("paging", {}).get("next")
            query = {}  # `next` already carries every parameter
            if not url:
                break
    return {"data": rows, "truncated": bool(url)}


def _act(ad_account_id: str) -> str:
    account = str(ad_account_id).strip()
    return account if account.startswith("act_") else f"act_{account}"


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "graph_version": GRAPH_VERSION})


@mcp.tool()
async def list_ad_accounts() -> Any:
    """Lists the ad accounts the system user can read (id, name, status, currency, timezone, business)."""
    return await _get(
        "me/adaccounts",
        {"fields": "id,account_id,name,account_status,currency,timezone_name,business{id,name}", "limit": 100},
        max_pages=MAX_PAGES,
    )


@mcp.tool()
async def list_campaigns(ad_account_id: str, effective_status: list[str] | None = None) -> Any:
    """Lists campaigns of an ad account with objective, status, budgets and dates.

    Args:
        ad_account_id: 'act_123' or '123'.
        effective_status: optional filter, e.g. ["ACTIVE", "PAUSED"].
    """
    params: dict[str, Any] = {
        "fields": "id,name,objective,status,effective_status,daily_budget,lifetime_budget,"
        "buying_type,start_time,stop_time,updated_time",
        "limit": 200,
    }
    if effective_status:
        params["effective_status"] = str(list(effective_status)).replace("'", '"')
    return await _get(f"{_act(ad_account_id)}/campaigns", params, max_pages=MAX_PAGES)


@mcp.tool()
async def get_insights(
    object_id: str,
    level: Literal["account", "campaign", "adset", "ad"] = "campaign",
    date_preset: str | None = "last_28d",
    since: str | None = None,
    until: str | None = None,
    fields: list[str] | None = None,
    breakdowns: list[str] | None = None,
    time_increment: str | None = None,
    action_attribution_windows: list[str] | None = None,
) -> Any:
    """Runs a Marketing API insights query.

    Args:
        object_id: ad account (must be 'act_123'), campaign, ad set or ad ID.
        level: aggregation level of the rows.
        date_preset: e.g. today, yesterday, last_7d, last_28d, last_90d, this_month.
            Ignored when since/until are given.
        since, until: YYYY-MM-DD, inclusive.
        fields: defaults to names + spend, impressions, clicks, inline_link_clicks,
            actions, cost_per_action_type. 'actions' holds lead / landing_page_view /
            onsite_conversion.* counts.
        breakdowns: e.g. ["publisher_platform"], ["age","gender"], ["region"].
        time_increment: "1" for daily rows, "monthly", or "all_days".
        action_attribution_windows: e.g. ["7d_click","1d_view"].
    """
    default_fields = [
        "account_id", "campaign_id", "campaign_name", "adset_id", "adset_name", "ad_id", "ad_name",
        "spend", "impressions", "reach", "clicks", "inline_link_clicks", "actions", "cost_per_action_type",
    ]
    params: dict[str, Any] = {
        "level": level,
        "fields": ",".join(fields or default_fields),
        "limit": 500,
    }
    if since and until:
        params["time_range"] = f'{{"since":"{since}","until":"{until}"}}'
    else:
        params["date_preset"] = date_preset or "last_28d"
    if breakdowns:
        params["breakdowns"] = ",".join(breakdowns)
    if time_increment:
        params["time_increment"] = time_increment
    if action_attribution_windows:
        params["action_attribution_windows"] = str(list(action_attribution_windows)).replace("'", '"')
    return await _get(f"{object_id}/insights", params, max_pages=MAX_PAGES)


def _destinations(creative: dict[str, Any]) -> list[str]:
    """Collects landing URLs from the usual places in a creative."""
    urls: list[str] = []
    spec = creative.get("object_story_spec") or {}
    link_data = spec.get("link_data") or {}
    for value in (
        creative.get("link_url"),
        link_data.get("link"),
        (link_data.get("call_to_action") or {}).get("value", {}).get("link"),
        ((spec.get("video_data") or {}).get("call_to_action") or {}).get("value", {}).get("link"),
    ):
        if value:
            urls.append(value)
    for attachment in link_data.get("child_attachments") or []:
        if attachment.get("link"):
            urls.append(attachment["link"])
    for link in (creative.get("asset_feed_spec") or {}).get("link_urls") or []:
        if link.get("website_url"):
            urls.append(link["website_url"])
    return list(dict.fromkeys(urls))


@mcp.tool()
async def list_ad_destinations(ad_account_id: str, only_active: bool = True) -> Any:
    """Lists ads with their landing URLs and UTM parameters (url_tags + URL query).

    Flags ads whose destination has no utm_source/utm_medium, ads pointing to
    WhatsApp (wa.me / api.whatsapp.com) or to Lead Ads forms, and the hostnames
    they send traffic to. This is the Meta side of "why is Meta traffic Direct
    in GA4" and "which LP/subdomain do Meta ads land on".

    Args:
        ad_account_id: 'act_123' or '123'.
        only_active: only ads with effective_status ACTIVE.
    """
    params: dict[str, Any] = {
        "fields": "id,name,effective_status,campaign{id,name,objective},adset{id,name,destination_type},"
        "creative{id,name,url_tags,link_url,object_story_spec,asset_feed_spec,call_to_action_type}",
        "limit": 100,
    }
    if only_active:
        params["effective_status"] = '["ACTIVE"]'
    result = await _get(f"{_act(ad_account_id)}/ads", params, max_pages=MAX_PAGES)

    ads = []
    for ad in result["data"]:
        creative = ad.get("creative") or {}
        url_tags = creative.get("url_tags") or ""
        tag_params = {k: v[0] for k, v in parse_qs(url_tags).items()}
        destinations = []
        for url in _destinations(creative):
            parsed = urlparse(url)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            utms = {k: (query.get(k) or tag_params.get(k)) for k in UTM_KEYS}
            destinations.append({
                "url": url,
                "host": parsed.hostname,
                "utm": {k: v for k, v in utms.items() if v},
                "missing_utm": [k for k in ("utm_source", "utm_medium", "utm_campaign") if not utms[k]],
                "is_whatsapp": bool(parsed.hostname and ("wa.me" in parsed.hostname or "whatsapp" in parsed.hostname)),
            })
        ads.append({
            "ad_id": ad.get("id"),
            "ad_name": ad.get("name"),
            "effective_status": ad.get("effective_status"),
            "campaign": ad.get("campaign"),
            "adset": ad.get("adset"),
            "url_tags": url_tags,
            "call_to_action_type": creative.get("call_to_action_type"),
            "destination_type": (ad.get("adset") or {}).get("destination_type"),
            "destinations": destinations,
        })
    return {"ads": ads, "truncated": result["truncated"]}


@mcp.tool()
async def list_pixels(ad_account_id: str) -> Any:
    """Lists the Meta pixels / datasets of an ad account (id, name, last_fired_time, creation)."""
    return await _get(
        f"{_act(ad_account_id)}/adspixels",
        {"fields": "id,name,last_fired_time,creation_time,is_unavailable,owner_business{id,name}", "limit": 100},
        max_pages=MAX_PAGES,
    )


@mcp.tool()
async def get_pixel_stats(
    pixel_id: str,
    aggregation: Literal["event", "host", "url", "event_source", "pixel_fire", "match_keys", "device_type"] = "event",
    start_time: str | None = None,
    end_time: str | None = None,
    event: str | None = None,
) -> Any:
    """Returns event counts received by a pixel/dataset, aggregated by a dimension.

    Use aggregation='host' to see which hostnames (site, LPs, subdomains,
    staging) fire the pixel; 'event_source' to compare browser pixel vs
    Conversions API (deduplication); 'event' for the event names (Lead,
    CompleteRegistration, Contact, custom events) to map to the GA4 taxonomy.

    Args:
        pixel_id: pixel / dataset ID (from list_pixels).
        aggregation: dimension to aggregate by.
        start_time, end_time: ISO date/time or unix seconds; default is the last ~48h.
        event: optional event name filter.
    """
    return await _get(
        f"{pixel_id}/stats",
        {"aggregation": aggregation, "start_time": start_time, "end_time": end_time, "event": event},
        max_pages=MAX_PAGES,
    )


@mcp.tool()
async def list_pages() -> Any:
    """Lists Facebook Pages the system user can access (needed for Lead Ads forms)."""
    return await _get("me/accounts", {"fields": "id,name,category", "limit": 100}, max_pages=MAX_PAGES)


@mcp.tool()
async def list_leadgen_forms(page_id: str) -> Any:
    """Lists Lead Ads (instant) forms of a Page: status, leads_count, questions, created_time.

    These leads never visit the site; they reach HubSpot through the Meta Lead
    Ads integration. Compare leads_count with HubSpot contacts whose source is
    the Meta integration. Lead PII is never returned by this server.

    Args:
        page_id: Facebook Page ID (from list_pages).
    """
    page = await _get(page_id, {"fields": "access_token"})
    page_token = page.get("access_token")
    if not page_token:
        raise MetaError("No Page access token: assign the Page to the system user with leads access.")
    return await _get(
        f"{page_id}/leadgen_forms",
        {"fields": "id,name,status,locale,leads_count,created_time,questions{key,type,label},"
                   "follow_up_action_url,thank_you_page{button_type,website_url}", "limit": 100},
        token=page_token,
        max_pages=MAX_PAGES,
    )


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
