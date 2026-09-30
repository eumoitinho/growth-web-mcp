---
name: ga4-event-hygiene
description: Limpa a visão de eventos e hostnames do GA4 - encontra eventos sujos, duplicados, desconhecidos, tráfego de subdomínios/staging, e propõe a taxonomia e o escopo corretos. Use quando falarem de "eventos sujos", "muitos eventos", "subdomínios sujando", ou antes de qualquer análise se os contratos ainda tiverem TODO.
---

# Higiene de eventos e hostnames

## 1. Configuração da propriedade (ga4)
- `get_account_summaries` → propriedades. `get_property_details`.
- `list_data_streams`: todos os streams e `defaultUri`. Mais de um web stream na
  mesma propriedade? Streams de LPs/subdomínios?
- `get_enhanced_measurement_settings` por stream: se `formInteractionsEnabled` e o
  GTM também manda eventos de form → duplicidade (form_start/form_submit).
  Idem `outboundClicksEnabled` × tags de clique, `scrollsEnabled` × scroll do GTM.
- `list_key_events`: key events que não são canônicos com `conversion: true`?
- `get_custom_dimensions_and_metrics`: parâmetros registrados × `required_params`.

## 2. Hostnames (BigQuery)
```sql
SELECT * FROM `PROJECT.growth_clean.rpt_hostnames`
WHERE last_seen >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY events DESC
```
Todo `unknown` com volume relevante precisa de regra em `config/site-scope.yaml`.
Sem BigQuery: `run_report` com dimensão `hostName`, métrica `eventCount`.

## 3. Eventos
```sql
SELECT event_name, event_status, canonical_event, site_scope,
       SUM(events) AS events, SUM(users) AS users, ANY_VALUE(sample_param_keys) AS params
FROM `PROJECT.growth_clean.rpt_event_hygiene`
WHERE last_seen >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3, 4
ORDER BY event_status = 'unknown' DESC, events DESC
```
Para cada `unknown`: é alias de um canônico? ruído? novo canônico legítimo? Olhe os
parâmetros e a origem no GTM (`gtm_tag list` e procure o nome do evento).

Sinais clássicos de sujeira:
- Mesmo evento com grafias diferentes (`Lead`, `lead`, `generate_lead`).
- Eventos `gtm.*` chegando ao GA4 (tag GA4 com "enviar todos os eventos do dataLayer").
- Um evento por botão/página (`click_banner_home_2`) → deveria ser `cta_click` + parâmetro.
- `generate_lead` > submissões reais no HubSpot → dispara no submit, não no sucesso.
- Volume em `staging` → filtro de tráfego interno/dev ausente no GA4.

## 4. Entregável
1. Diff proposto para `config/event-taxonomy.yaml` e `config/site-scope.yaml`
   (abra PR com `scripts/bq-apply.sh` como passo de teste).
2. Lista de ações fora do repo: desligar opções de enhanced measurement, criar filtro
   de dados de tráfego interno/dev, ajustar tags do GTM (ver `gtm-container-audit`),
   registrar custom dimensions faltantes.
3. Plano para a migração Next.js: somente eventos canônicos com `required_params`.
