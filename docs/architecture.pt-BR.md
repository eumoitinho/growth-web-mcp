# Arquitetura e integrações

```
                        ┌──────────────── Google Cloud (Cloud Run, IAM) ────────────────┐
 Agente                 │                                                               │
 (Claude Code,          │  growth-mcp-ga4 ─────── analytics-mcp (Google)  ──► GA4 Admin/Data API
  ADK, ...)  ──HTTPS──► │  growth-mcp-google-ads ─ google-ads-mcp (Google) ──► Google Ads API
                        │  growth-mcp-meta ────── servidor próprio (leitura) ──► Meta Marketing API
  + skills   ID token   │  growth-mcp-gtm ─────── gtm-mcp-core (Stape)    ──► Tag Manager API
                        │  growth-mcp-hubspot ─── @hubspot/mcp-server     ──► HubSpot API
                        │  growth-mcp-site-browser  chrome-devtools-mcp   ──► site (headless Chrome)
                        │                                                               │
                        │  BigQuery MCP (gerenciado pelo Google) ──► growth_clean (views) ◄── export GA4
                        └───────────────────────────────────────────────────────────────┘
```

## O que é cada peça

| Serviço | Upstream (pinado) | O que este repo adiciona |
|---|---|---|
| `ga4` | [googleanalytics/google-analytics-mcp](https://github.com/googleanalytics/google-analytics-mcp) `analytics-mcp==0.7.0` | Transporte Streamable HTTP (upstream é só stdio) + 5 tools Admin read-only: `list_data_streams`, `get_enhanced_measurement_settings`, `list_key_events`, `list_channel_groups`, `get_data_retention_settings` |
| `google-ads` | [googleads/google-ads-mcp](https://github.com/googleads/google-ads-mcp) `google-ads-mcp==0.0.4` | Modo HTTP + ADC com IAM do Cloud Run (upstream oferece stdio ou OAuth proxy; este continua disponível com `ADS_MCP_MODE=oauth`) |
| `gtm` | [stape-io/google-tag-manager-mcp-server](https://github.com/stape-io/google-tag-manager-mcp-server) `google-tag-manager-mcp-core@2.1.1` | ADC com escopo mínimo + política por `action` (read / write / delete / publish) |
| `hubspot` | [@hubspot/mcp-server](https://www.npmjs.com/package/@hubspot/mcp-server) `0.4.0` (oficial HubSpot) | Filtro read/write + tools de Forms, Submissões e Pipelines (não existem no upstream e são o coração do problema de funil) |
| `meta` | Graph Marketing API v26 (sem servidor open source oficial auto-hospedável) | Servidor próprio mínimo, só leitura, token de system user: insights, UTMs/destinos dos anúncios, pixel por evento/host/origem, Lead Ads. Escrita via [MCP oficial do Meta](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-overview) (`mcp.facebook.com/ads`) |
| `site-browser` | [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) `1.10.1` + [supergateway](https://github.com/supercorp-ai/supergateway) `4.0.0` | Imagem com Chrome headless; uma sessão MCP = um Chrome isolado |
| `bigquery` | [BigQuery MCP gerenciado](https://cloud.google.com/bigquery/docs/use-bigquery-mcp) (`https://bigquery.googleapis.com/mcp`) | Nada para hospedar. Este repo cria a **superfície limpa** (`bigquery/`) que o agente consulta |
| `gateway` | [FastMCP](https://github.com/PrefectHQ/fastmcp) `4.0.10` (proxy + OAuth proxy do Google) | URL pública única para o **conector do claude.ai**: login Google restrito aos domínios configurados, repassa as chamadas aos servidores de leitura (privados) e ao WordPress. Ver [`docs/claude-web-connector.md`](claude-web-connector.md) |

HubSpot também oferece o servidor remoto oficial (`https://mcp.hubspot.com`, OAuth por
usuário) — ótimo para pessoas no Claude/ChatGPT. O serviço deste repo existe para o
agente ter uma identidade estável, auditável e com escopo controlado.

## A "superfície limpa"

O GA4 bruto é sujo (eventos duplicados, nomes legados, LPs e subdomínios misturados).
Em vez de o agente reaprender isso a cada pergunta, a limpeza é **contrato versionado**:

- [`config/site-scope.yaml`](../config/site-scope.yaml) — hostname → `website | blog | landing_pages | product | staging | external`.
- [`config/event-taxonomy.yaml`](../config/event-taxonomy.yaml) — `event_name` → canônico / alias / auto / review / noise.
- [`config/hubspot-funnel.yaml`](../config/hubspot-funnel.yaml) — para onde cada form/CTW *deveria* levar o contato.

`scripts/bq-apply.sh` transforma os YAMLs em views sobre o export GA4 →
`growth_clean.stg_events`, `fct_sessions`, `fct_conversions`, `rpt_*`
(detalhes em [`bigquery/README.md`](../bigquery/README.md)). O agente analisa ali;
quando encontra algo novo, propõe PR nos YAMLs. Os mesmos contratos servem de
especificação de tagueamento para o site Next.js.

## O agente

- [`CLAUDE.md`](../CLAUDE.md) — papel, ferramentas, regras.
- [`.claude/skills/`](../.claude/skills) — playbooks: `inbound-funnel-audit`,
  `meta-ads-tracking`, `ga4-event-hygiene`, `gtm-container-audit`, `hubspot-form-routing`,
  `site-tagging-qa`, `site-performance`.
- [`.mcp.json`](../.mcp.json) — conexão com os servidores (Claude Code). A autenticação
  é feita por [`scripts/mcp-auth-header.sh`](../scripts/mcp-auth-header.sh) com o seu
  `gcloud`.

Qualquer cliente MCP com Streamable HTTP funciona (Gemini CLI, ADK, etc.) — basta
enviar um ID token do Google (`Authorization: Bearer`) de alguém com `roles/run.invoker`.

## Leitura por padrão, escrita opcional

Tudo sobe **somente leitura**. Escrita (GTM e HubSpot) é um segundo conjunto de
serviços, com outras service accounts, outros tokens e outra lista de quem pode usar.
Escrita no Meta usa o MCP oficial hospedado pelo Meta (OAuth por pessoa).
Ver [`docs/write-access.md`](write-access.md).

