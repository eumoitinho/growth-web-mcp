-- Which hostnames send data, how they are classified, and how much.
-- 'unknown' rows mean config/site-scope.yaml needs a rule.
CREATE OR REPLACE VIEW `{{project}}.{{clean}}.rpt_hostnames`
OPTIONS (description = 'Hostnames sending hits, with site_scope classification') AS
SELECT
  hostname,
  site_scope,
  ARRAY_AGG(DISTINCT CAST(stream_id AS STRING) IGNORE NULLS) AS stream_ids,
  COUNT(*) AS events,
  COUNTIF(event_name = 'page_view') AS page_views,
  COUNT(DISTINCT session_key) AS sessions,
  COUNTIF(is_conversion) AS conversions,
  MIN(event_date) AS first_seen,
  MAX(event_date) AS last_seen
FROM `{{project}}.{{clean}}.stg_events`
GROUP BY hostname, site_scope;
