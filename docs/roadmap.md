# Roadmap

1. **Calibrar contratos (semana 1).** Rodar `ga4-event-hygiene` e
   `gtm-container-audit`; fechar os TODO de `config/*.yaml` com PRs.
2. **HubSpot → BigQuery.** Hoje a reconciliação lead a lead é feita pelo agente via
   API (amostras). Levar contatos, submissões e deals para o BigQuery (ex.: Cloud Run
   Job diário com a mesma API, ou um conector como Airbyte/Fivetran) permite
   `fct_leads` juntando `fct_conversions` ↔ contato por `hubspot_form_id` + e-mail
   hash + timestamp, e medir o funil até MQL/SQL/deal.
3. **Search Console.** Queries e páginas orgânicas (export nativo do GSC para
   BigQuery) para fechar o topo orgânico.
4. **WordPress.** Feito: MCP Adapter oficial + abilities só leitura em `wordpress/` (instalação em `wordpress/README.md`).
5. **Next.js.** Quando o repo do site novo existir, o agente usa os contratos como
   spec: dataLayer tipado gerado de `event-taxonomy.yaml` e um teste de QA
   (`site-tagging-qa`) no preview de cada PR.
6. **Agente agendado.** Um Cloud Run Job (ADK ou Claude Agent SDK) com a SA
   `growth-agent`, rodando higiene + funil semanalmente e publicando o relatório.
7. **Materializar.** Se o custo/latência das views crescer, trocar `stg_events` e
   `fct_sessions` por tabelas particionadas (scheduled queries ou dbt).
