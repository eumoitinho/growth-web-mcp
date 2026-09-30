-- One row per GA4 event, flattened, classified by site scope and event taxonomy.
-- Everything downstream reads from here; never query events_* directly for analysis.
CREATE OR REPLACE VIEW `{{project}}.{{clean}}.stg_events`
OPTIONS (description = 'Flattened GA4 export (last {{lookback_days}} days) with site_scope and canonical_event') AS
WITH raw AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    TIMESTAMP_MICROS(event_timestamp) AS event_ts,
    event_name,
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_number') AS ga_session_number,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS page_location,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_referrer') AS page_referrer,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_title') AS page_title,
    (SELECT COALESCE(value.string_value, CAST(value.int_value AS STRING)) FROM UNNEST(event_params) WHERE key = 'session_engaged') AS session_engaged,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec') AS engagement_time_msec,
    (SELECT COALESCE(value.string_value, CAST(value.int_value AS STRING)) FROM UNNEST(event_params) WHERE key = 'form_id') AS form_id,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'form_name') AS form_name,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'hubspot_form_id') AS hubspot_form_id,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'lead_type') AS lead_type,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'cta_location') AS cta_location,
    (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'link_url') AS link_url,
    COALESCE(device.web_info.hostname, NET.HOST((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))) AS hostname,
    device.category AS device_category,
    geo.country AS country,
    stream_id,
    collected_traffic_source.manual_source,
    collected_traffic_source.manual_medium,
    collected_traffic_source.manual_campaign_name,
    collected_traffic_source.manual_term,
    collected_traffic_source.manual_content,
    collected_traffic_source.gclid AS collected_gclid,
    traffic_source.source AS first_user_source,
    traffic_source.medium AS first_user_medium,
    traffic_source.name AS first_user_campaign,
    ARRAY(SELECT key FROM UNNEST(event_params) ORDER BY key) AS param_keys
  FROM `{{ga4_project}}.{{ga4_dataset}}.events_*`
  WHERE REGEXP_CONTAINS(_TABLE_SUFFIX, r'^\d{8}$')  -- daily tables only (skip events_intraday_*)
    AND _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL {{lookback_days}} DAY))
)
SELECT
  r.* EXCEPT (manual_source, manual_medium, manual_campaign_name, manual_term, manual_content, collected_gclid),
  -- UTMs: what GA4 collected, falling back to the raw URL (custom forms and SPA
  -- navigations sometimes lose them).
  COALESCE(manual_source, REGEXP_EXTRACT(page_location, r'[?&]utm_source=([^&#]*)')) AS utm_source,
  COALESCE(manual_medium, REGEXP_EXTRACT(page_location, r'[?&]utm_medium=([^&#]*)')) AS utm_medium,
  COALESCE(manual_campaign_name, REGEXP_EXTRACT(page_location, r'[?&]utm_campaign=([^&#]*)')) AS utm_campaign,
  COALESCE(manual_term, REGEXP_EXTRACT(page_location, r'[?&]utm_term=([^&#]*)')) AS utm_term,
  COALESCE(manual_content, REGEXP_EXTRACT(page_location, r'[?&]utm_content=([^&#]*)')) AS utm_content,
  COALESCE(collected_gclid, REGEXP_EXTRACT(page_location, r'[?&]gclid=([^&#]*)')) AS gclid,
  IF(ga_session_id IS NULL, NULL, CONCAT(user_pseudo_id, '.', CAST(ga_session_id AS STRING))) AS session_key,
  REGEXP_EXTRACT(page_location, r'^https?://[^/?#]+([^?#]*)') AS page_path,
  NET.HOST(page_referrer) AS referrer_host,
  {{site_scope(r.hostname)}} AS site_scope,
  COALESCE(t.canonical_event, r.event_name) AS canonical_event,
  COALESCE(t.status, 'unknown') AS event_status,
  t.funnel_stage,
  COALESCE(t.is_conversion, FALSE) AS is_conversion
FROM raw AS r
LEFT JOIN `{{project}}.{{clean}}.dim_event_taxonomy` AS t USING (event_name);
