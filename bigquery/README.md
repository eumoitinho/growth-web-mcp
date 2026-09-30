# Superfície limpa (BigQuery)

Views sobre o export GA4 (`analytics_<property>.events_*`), geradas a partir dos
contratos em `config/`. Aplicar:

```bash
PROJECT_ID=<projeto> scripts/bq-apply.sh            # renderiza em bigquery/build/ e aplica
PROJECT_ID=<projeto> scripts/bq-apply.sh --dry-run  # só valida
```

O export pode estar em outro projeto (`export_project` em `site-scope.yaml` ou
`GA4_PROJECT`); o `growth_clean` precisa estar na **mesma localização** dele.

Variáveis opcionais: `GA4_PROJECT` / `GA4_DATASET` (padrão: `site-scope.yaml`), `CLEAN_DATASET`
(`growth_clean`), `LOOKBACK_DAYS` (180 — janela máxima que as views enxergam).

| Objeto | Grão | Uso |
|---|---|---|
| `dim_event_taxonomy` | event_name | tabela gerada de `event-taxonomy.yaml` |
| `stg_events` | evento | base: parâmetros achatados, `site_scope`, `canonical_event`, `event_status`, UTMs (com fallback da URL) |
| `fct_sessions` | sessão | landing, UTM, `channel`, contagens de funil, `crossed_scopes` |
| `fct_conversions` | conversão | eventos `conversion: true` + aquisição da sessão |
| `rpt_event_hygiene` | evento × hostname × stream | triagem de sujeira |
| `rpt_hostnames` | hostname | classificação de escopo e volume |
| `rpt_landing_pages` | dia × landing × aquisição | performance de LPs |
| `rpt_inbound_funnel` | dia × escopo × canal | funil sessões → lead / CTW |

Notas:
- `channel` é um agrupamento simplificado e determinístico (documentado no SQL), não o
  default channel group do GA4 — o objetivo é ser explicável e estável entre sistemas.
- Tabelas `events_intraday_*` são ignoradas (dados do dia chegam no dia seguinte).
- Mudou um YAML → rode `bq-apply.sh` de novo. Nunca edite `bigquery/build/`.
