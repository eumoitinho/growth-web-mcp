-- Triage surface for dirty events: what fires, where, with which params.
-- Sort by event_status = 'unknown' / 'review' first.
CREATE OR REPLACE VIEW `{{project}}.{{clean}}.rpt_event_hygiene`
OPTIONS (description = 'event_name x site_scope x hostname volume, status and parameter keys') AS
SELECT
  event_name,
  canonical_event,
  event_status,
  site_scope,
  hostname,
  stream_id,
  COUNT(*) AS events,
  COUNT(DISTINCT user_pseudo_id) AS users,
  MIN(event_date) AS first_seen,
  MAX(event_date) AS last_seen,
  ARRAY_TO_STRING(ANY_VALUE(param_keys), ',') AS sample_param_keys
FROM `{{project}}.{{clean}}.stg_events`
GROUP BY event_name, canonical_event, event_status, site_scope, hostname, stream_id;
