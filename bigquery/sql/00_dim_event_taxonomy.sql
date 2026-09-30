-- Generated from config/event-taxonomy.yaml by scripts/render_bq.py. Do not edit the build output.
CREATE OR REPLACE TABLE `{{project}}.{{clean}}.dim_event_taxonomy`
OPTIONS (description = 'event_name -> canonical event/status. Source: config/event-taxonomy.yaml') AS
SELECT *
FROM UNNEST(ARRAY<STRUCT<event_name STRING, canonical_event STRING, status STRING, funnel_stage STRING, is_conversion BOOL, note STRING>>[
{{event_taxonomy_rows}}
]);
