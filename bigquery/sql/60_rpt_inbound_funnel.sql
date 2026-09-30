-- Daily inbound funnel of the WEBSITE (landing_scope = 'website' by default in
-- analyses; other scopes are kept so LPs can be compared side by side).
CREATE OR REPLACE VIEW `{{project}}.{{clean}}.rpt_inbound_funnel`
OPTIONS (description = 'Daily funnel: sessions -> engaged -> CTA -> form_start -> lead / CTW, by channel and landing scope') AS
SELECT
  session_date,
  landing.site_scope AS landing_scope,
  channel,
  COUNT(*) AS sessions,
  COUNTIF(engaged) AS engaged_sessions,
  COUNTIF(cta_clicks > 0) AS cta_sessions,
  COUNTIF(form_starts > 0) AS form_start_sessions,
  COUNTIF(leads > 0) AS lead_sessions,
  COUNTIF(ctw_clicks > 0) AS ctw_sessions,
  COUNTIF(sign_ups > 0) AS sign_up_sessions,
  SAFE_DIVIDE(COUNTIF(leads > 0 OR ctw_clicks > 0), COUNT(*)) AS inbound_conversion_rate,
  SAFE_DIVIDE(COUNTIF(leads > 0), NULLIF(COUNTIF(form_starts > 0), 0)) AS form_completion_rate
FROM `{{project}}.{{clean}}.fct_sessions`
GROUP BY 1, 2, 3;
