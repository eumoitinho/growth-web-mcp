---
name: hubspot-form-routing
description: Investiga por que formulários do site/LPs (incluindo formulários customizados via Forms API) ou conversas de click-to-WhatsApp caem no funil/lifecycle/owner errado no HubSpot, e por que a origem aparece como Offline/Direct. Use para qualquer dúvida de "lead caiu errado", "MQL errado", "origem errada no HubSpot".
---

# Roteamento de formulários no HubSpot

O esperado está em `config/hubspot-funnel.yaml`. Cada entrada = uma porta de entrada.

## 1. Mapear forms
- `hubspot-list-forms` (formTypes all) → nome, id, tipo. `captured` = formulário
  não-HubSpot coletado pelo script de tracking (comum no WordPress; costuma duplicar
  com o envio via API).
- Para cada `hubspot_form_id` do contrato, `hubspot-get-form`:
  - campos ocultos existem? (`utm_*`, `gclid`, `lead_type`, `form_origin`)
  - `configuration.lifecycleStages` (o form força um estágio?)
  - opções de criação/atualização de contato e notificações.
- Forms usados no site que NÃO estão no contrato = achado.

## 2. Ver o que chega
- `hubspot-list-form-submissions` do form: `pageUrl` (qual site/LP/subdomínio),
  valores dos campos ocultos (vazios = UTMs se perdendo no front).
- Formulário customizado via Forms API (`/submissions/v3/integration/submit`): a
  submissão precisa de `context.hutk` (cookie `hubspotutk`), `pageUri` e `pageName`.
  Sem `hutk`: o contato não é ligado à visita → origem `OFFLINE`/`Direct` e sem
  histórico de páginas. Confirme no `site-browser` (payload do request, sem enviar em prod).

## 3. O que acontece depois do submit
- `hubspot-list-workflows` / `hubspot-get-workflow`: workflows cujo gatilho é
  submissão do form ou propriedade que ele seta. Procure:
  - dois workflows setando `lifecyclestage`/`hs_lead_status` em conflito;
  - workflow que pula estágio (lead → SQL direto) ou re-inscreve contatos;
  - atribuição de owner / criação de deal no pipeline errado (`hubspot-list-pipelines`).
- Contatos recentes do form (`hubspot-search-objects` filtrando
  `recent_conversion_event_name` ou `first_conversion_event_name` contendo o nome do
  form) com as `attribution_properties`. Compare com `expected`.

## 4. Click-to-WhatsApp
- `ctw_click` no GA4 (`fct_conversions`) × contatos criados pela integração no
  mesmo período. Sem código de referência na mensagem pré-preenchida, a atribuição
  se perde por desenho (`wa.me` não carrega UTM) — proponha o `attribution_carrier`.

## 5. Entregável
Por porta de entrada: esperado × observado (lifecycle, lead status, owner, pipeline,
fonte), causa raiz (form config, workflow, front sem hutk/UTM, duplicidade captured
+ API) e correção. Contatos afetados: contagem e IDs de amostra.

## Escrita (somente com `hubspot-write` carregado e "ok" explícito)
Correções em lote de contatos (`hubspot-batch-update-objects`) no máximo 100 por vez,
com a lista de IDs e valores antes/depois registrada na conversa.
