---
name: inbound-funnel-audit
description: Auditoria ponta a ponta do inbound do site - UTM/Ads -> landing -> eventos GA4 -> formulário ou click-to-WhatsApp -> contato e lifecycle no HubSpot. Use para perguntas amplas ("o inbound está funcionando?", "por que os leads caíram?", "de onde vêm os MQLs?").
---

# Auditoria do funil de inbound

Objetivo: um diagnóstico com números reconciliados entre Ads, GA4 e HubSpot, e a
lista priorizada do que quebra a cadeia.

## 1. Escopo e janela
- Janela padrão: últimos 28 dias completos (termina ontem). Diga a janela usada.
- Escopo padrão: `site_scope = 'website'`. Mostre LPs (`landing_pages`) em separado.
- Leia `config/site-scope.yaml`, `config/event-taxonomy.yaml`, `config/hubspot-funnel.yaml`.

## 2. Topo: aquisição (BigQuery + Google Ads)
- `rpt_inbound_funnel` agrupado por `channel` e `landing_scope`.
- Google Ads (`search`): cliques e conversões por campanha na mesma janela, ex.:
  `SELECT campaign.name, metrics.clicks, metrics.conversions FROM campaign WHERE segments.date DURING LAST_30_DAYS`.
- Compare cliques de Ads × sessões `channel = 'Paid Search - Google Ads'`. Perda
  > 30% sugere gclid/UTM se perdendo (redirects, auto-tagging, consent) — anote.
- Meta (`get_insights` level campaign, mesma janela): `inline_link_clicks` e
  `actions` (landing_page_view, lead) × sessões `channel = 'Paid Social'`. Tráfego
  Meta caindo em Direct/Referral = anúncios sem UTM (`list_ad_destinations`).
  Detalhes na skill `meta-ads-tracking`.

## 3. Meio: site e eventos
- `rpt_hostnames`: algum `unknown` com volume? Tráfego de staging contaminando?
- `rpt_event_hygiene`: volume de `unknown`/`review`/`alias` por hostname.
- `fct_sessions`: % de sessões com `crossed_scopes` (site ↔ LP ↔ produto) — indica
  quebra de sessão/atribuição entre subdomínios (cross-domain / cookies).

## 4. Conversão
- `fct_conversions` por `canonical_event`, `form_id`/`hubspot_form_id`, `lead_type`, `channel`.
- Conversões sem `hubspot_form_id` ou `form_id` = não dá para casar com o HubSpot.
- `ctw_click` por `cta_location`: quais botões de WhatsApp geram intenção.

## 5. Fundo: HubSpot
- Para cada entrada de `hubspot-funnel.yaml`: `hubspot-list-form-submissions`
  (mesma janela) → contagem por `pageUrl` host.
- Compare submissões HubSpot × `generate_lead` GA4 do mesmo form. Diferença > 15%
  = evento disparando no lugar errado (submit vs sucesso) ou form sem evento.
- Amostre contatos recentes (`hubspot-search-objects`, `createdate` na janela) com
  as `attribution_properties`; distribuição de `hs_analytics_source` e `lifecyclestage`.
  Muito `OFFLINE`/`DIRECT_TRAFFIC` vindo de formulário do site = hutk/cookie não enviado.
- Para desvios de lifecycle, siga a skill `hubspot-form-routing`.

## 6. Entregável
Tabela de reconciliação (Ads cliques → sessões → form_start → generate_lead →
submissões HubSpot → contatos → MQL), depois achados priorizados:

| # | Achado | Impacto estimado | Evidência | Correção | Dono (site/GTM/GA4/HubSpot) |

Termine com as mudanças propostas nos YAMLs de contrato, se houver.
