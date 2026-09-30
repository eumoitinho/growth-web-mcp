-- One row per session: landing page, acquisition, engagement and funnel counts.
-- Noise events are excluded; alias events count as their canonical event.
CREATE OR REPLACE VIEW `{{project}}.{{clean}}.fct_sessions`
OPTIONS (description = 'Sessions with landing page, UTM/referrer acquisition, channel and inbound funnel counts') AS
WITH agg AS (
  SELECT
    session_key,
    ANY_VALUE(user_pseudo_id) AS user_pseudo_id,
    MIN(event_date) AS session_date,
    MIN(event_ts) AS session_start_ts,
    ARRAY_AGG(
      IF(event_name = 'page_view', STRUCT(hostname, site_scope, page_location, page_path, referrer_host), NULL)
      IGNORE NULLS ORDER BY event_ts LIMIT 1
    )[SAFE_OFFSET(0)] AS landing,
    ARRAY_AGG(
      IF(utm_source IS NOT NULL OR gclid IS NOT NULL,
         STRUCT(utm_source AS source, utm_medium AS medium, utm_campaign AS campaign, utm_term AS term, utm_content AS content, gclid),
         NULL)
      IGNORE NULLS ORDER BY event_ts LIMIT 1
    )[SAFE_OFFSET(0)] AS utm,
    ANY_VALUE(device_category) AS device_category,
    ANY_VALUE(country) AS country,
    MIN(ga_session_number) AS ga_session_number,
    COUNTIF(event_name = 'page_view') AS page_views,
    COALESCE(LOGICAL_OR(session_engaged = '1'), FALSE) AS engaged,
    SUM(engagement_time_msec) / 1000 AS engagement_seconds,
    COUNTIF(canonical_event = 'cta_click') AS cta_clicks,
    COUNTIF(canonical_event = 'form_start') AS form_starts,
    COUNTIF(canonical_event = 'generate_lead') AS leads,
    COUNTIF(canonical_event = 'ctw_click') AS ctw_clicks,
    COUNTIF(canonical_event = 'sign_up') AS sign_ups,
    COUNTIF(is_conversion) AS conversions,
    ARRAY_AGG(DISTINCT site_scope IGNORE NULLS) AS scopes_touched
  FROM `{{project}}.{{clean}}.stg_events`
  WHERE session_key IS NOT NULL
    AND event_status != 'noise'
  GROUP BY session_key
)
SELECT
  agg.*,
  -- Simplified channel grouping, deterministic and explainable. Own-site
  -- referrers are treated as no referrer (cross-subdomain navigation).
  CASE
    WHEN utm.gclid IS NOT NULL THEN 'Paid Search - Google Ads'
    WHEN REGEXP_CONTAINS(LOWER(utm.medium), r'^(cpc|ppc|paid|paid[_-].*|display|cpm|banner)$')
      AND REGEXP_CONTAINS(LOWER(utm.source), r'google|bing|youtube') THEN 'Paid Search/Display - Other'
    WHEN REGEXP_CONTAINS(LOWER(utm.medium), r'^(cpc|ppc|paid|paid[_-].*|cpm|display|banner)$')
      AND REGEXP_CONTAINS(LOWER(utm.source), r'facebook|instagram|meta|fb|ig|linkedin|tiktok|twitter|x\.com') THEN 'Paid Social'
    WHEN REGEXP_CONTAINS(LOWER(utm.medium), r'social') THEN 'Organic Social'
    WHEN REGEXP_CONTAINS(LOWER(utm.medium), r'e-?mail|newsletter') OR REGEXP_CONTAINS(LOWER(utm.source), r'hubspot|hs_email|newsletter') THEN 'Email'
    WHEN REGEXP_CONTAINS(LOWER(utm.medium), r'whatsapp|wpp') OR REGEXP_CONTAINS(LOWER(utm.source), r'whatsapp|wpp') THEN 'WhatsApp'
    WHEN REGEXP_CONTAINS(LOWER(utm.medium), r'^(referral|partner|parceiro|affiliate)$') THEN 'Referral / Partner'
    WHEN utm.source IS NOT NULL THEN 'Other Campaign'
    WHEN {{site_scope(landing.referrer_host)}} NOT IN ('unknown', 'external') THEN 'Direct / Internal'
    WHEN REGEXP_CONTAINS(landing.referrer_host, r'(^|\.)(google|bing|yahoo|duckduckgo|ecosia|yandex)\.') THEN 'Organic Search'
    WHEN REGEXP_CONTAINS(landing.referrer_host, r'(facebook|instagram|linkedin|lnkd\.in|t\.co|tiktok|youtube)\.') THEN 'Organic Social'
    WHEN REGEXP_CONTAINS(landing.referrer_host, r'chatgpt\.com|openai\.com|perplexity\.ai|gemini\.google|claude\.ai|copilot\.microsoft') THEN 'AI Assistants'
    WHEN landing.referrer_host IS NOT NULL THEN 'Referral'
    ELSE 'Direct / Unknown'
  END AS channel,
  ARRAY_LENGTH(scopes_touched) > 1 AS crossed_scopes
FROM agg;
