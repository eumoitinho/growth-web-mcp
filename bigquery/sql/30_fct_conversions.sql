-- Every conversion event with the acquisition of the session it happened in.
-- This is the GA4 side of the join with HubSpot (form_id / hubspot_form_id,
-- timestamp, page) that the hubspot-form-routing skill performs.
CREATE OR REPLACE VIEW `{{project}}.{{clean}}.fct_conversions`
OPTIONS (description = 'Conversion events (per config/event-taxonomy.yaml) with session acquisition') AS
SELECT
  e.event_date,
  e.event_ts,
  e.test_run_id,
  e.submission_id,
  e.event_id,
  e.session_key,
  e.user_pseudo_id,
  e.canonical_event,
  e.event_name AS raw_event_name,
  e.event_status,
  e.hostname,
  e.site_scope,
  e.page_path,
  e.page_location,
  e.form_id,
  e.form_name,
  e.hubspot_form_id,
  e.lead_type,
  e.cta_location,
  e.link_url,
  s.channel,
  s.utm.source AS session_source,
  s.utm.medium AS session_medium,
  s.utm.campaign AS session_campaign,
  s.utm.gclid IS NOT NULL AS has_gclid,
  s.landing.site_scope AS landing_scope,
  s.landing.hostname AS landing_hostname,
  s.landing.page_path AS landing_page_path,
  s.ga_session_number,
  s.device_category
FROM `{{project}}.{{clean}}.stg_events` AS e
LEFT JOIN `{{project}}.{{clean}}.fct_sessions` AS s USING (session_key)
WHERE e.is_conversion;
