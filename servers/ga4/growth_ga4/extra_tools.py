"""Read-only GA4 Admin tools missing from upstream analytics-mcp.

Upstream covers reporting (run_report, funnels, realtime) but not the property
configuration that explains *why* events are dirty: which data streams exist,
what enhanced measurement is auto-collecting (a common source of duplicated
form_submit / click / scroll events next to GTM tags), which events are marked
as key events, and how channels are grouped.

All calls reuse upstream's credential handling (analytics.readonly scope).
"""

import asyncio
from typing import Any, Dict, List

from analytics_mcp.tools.client import (
    create_admin_alpha_api_client,
    create_admin_api_client,
)
from analytics_mcp.tools.utils import construct_property_rn, proto_to_dict


async def list_data_streams(property_id: int | str) -> List[Dict[str, Any]]:
    """Lists the data streams (web/app) of a GA4 property.

    Use it to find every measurement ID (G-XXXX) and default URI feeding the
    property. Streams pointing to subdomains or landing-page builders are a
    frequent cause of mixed traffic in reports.

    Args:
        property_id: The Google Analytics property ID. Accepted formats are:
          - A number
          - A string consisting of 'properties/' followed by a number
    """
    parent = construct_property_rn(property_id)

    def _sync_call():
        pager = create_admin_api_client().list_data_streams(parent=parent)
        return [proto_to_dict(stream) for stream in pager]

    return await asyncio.to_thread(_sync_call)


async def get_enhanced_measurement_settings(
    property_id: int | str, data_stream_id: int | str
) -> Dict[str, Any]:
    """Returns the enhanced measurement settings of a web data stream.

    Enhanced measurement makes gtag/GA4 emit page_view, scroll, click
    (outbound), view_search_results, video_*, file_download, form_start and
    form_submit automatically. When GTM also sends these events the property
    ends up with duplicates, so check this before blaming GTM.

    Args:
        property_id: The Google Analytics property ID (number or
          'properties/<number>').
        data_stream_id: The numeric data stream ID (from list_data_streams).
    """
    name = (
        f"{construct_property_rn(property_id)}/dataStreams/"
        f"{str(data_stream_id).split('/')[-1]}/enhancedMeasurementSettings"
    )

    def _sync_call():
        return create_admin_alpha_api_client().get_enhanced_measurement_settings(
            name=name
        )

    return proto_to_dict(await asyncio.to_thread(_sync_call))


async def list_key_events(property_id: int | str) -> List[Dict[str, Any]]:
    """Lists the events marked as key events (conversions) in a GA4 property.

    Args:
        property_id: The Google Analytics property ID (number or
          'properties/<number>').
    """
    parent = construct_property_rn(property_id)

    def _sync_call():
        pager = create_admin_api_client().list_key_events(parent=parent)
        return [proto_to_dict(key_event) for key_event in pager]

    return await asyncio.to_thread(_sync_call)


async def list_channel_groups(property_id: int | str) -> List[Dict[str, Any]]:
    """Lists the channel groups (default and custom) of a GA4 property.

    Args:
        property_id: The Google Analytics property ID (number or
          'properties/<number>').
    """
    parent = construct_property_rn(property_id)

    def _sync_call():
        pager = create_admin_alpha_api_client().list_channel_groups(
            parent=parent
        )
        return [proto_to_dict(group) for group in pager]

    return await asyncio.to_thread(_sync_call)


async def get_data_retention_settings(property_id: int | str) -> Dict[str, Any]:
    """Returns the event/user data retention settings of a GA4 property.

    Explorations and funnel reports cannot look further back than this.

    Args:
        property_id: The Google Analytics property ID (number or
          'properties/<number>').
    """
    name = f"{construct_property_rn(property_id)}/dataRetentionSettings"

    def _sync_call():
        return create_admin_api_client().get_data_retention_settings(name=name)

    return proto_to_dict(await asyncio.to_thread(_sync_call))


EXTRA_TOOLS = [
    list_data_streams,
    get_enhanced_measurement_settings,
    list_key_events,
    list_channel_groups,
    get_data_retention_settings,
]
