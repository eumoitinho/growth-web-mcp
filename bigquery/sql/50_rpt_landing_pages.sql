CREATE OR REPLACE VIEW `{{project}}.{{clean}}.rpt_landing_pages`
OPTIONS (description = 'Landing page x acquisition: sessions, engagement and inbound conversions') AS
SELECT
  session_date,
  landing.site_scope AS landing_scope,
  landing.hostname AS landing_hostname,
  landing.page_path AS landing_page_path,
  channel,
  utm.source AS source,
  utm.medium AS medium,
  utm.campaign AS campaign,
  device_category,
  COUNT(*) AS sessions,
  COUNTIF(engaged) AS engaged_sessions,
  COUNTIF(form_starts > 0) AS sessions_with_form_start,
  COUNTIF(leads > 0) AS sessions_with_lead,
  COUNTIF(ctw_clicks > 0) AS sessions_with_ctw,
  COUNTIF(conversions > 0) AS converting_sessions
FROM `{{project}}.{{clean}}.fct_sessions`
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9;
