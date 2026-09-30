---
name: meta-ads-tracking
description: Audita o rastreamento de Meta Ads (Facebook/Instagram) no inbound - UTMs e destinos dos anúncios, qual LP/subdomínio recebe o tráfego, pixel x Conversions API (duplicidade, deduplicação, hosts), anúncios click-to-WhatsApp e formulários de Lead Ads sincronizados com o HubSpot. Use para "tráfego do Meta caindo como Direct", "leads do Meta não batem", "pixel duplicado", "Lead Ads caindo errado no HubSpot".
---

# Rastreamento Meta Ads

IDs em `config/site-scope.yaml` → `meta`. Sem IDs: `list_ad_accounts`, `list_pixels`, `list_pages`.

## 1. Anúncios → site (UTMs)
- `list_ad_destinations` (anúncios ativos): para cada anúncio, `destinations[].host`,
  `utm` e `missing_utm`.
  - Sem `utm_source/utm_medium` → no GA4 vira Referral (`l.facebook.com`, `lm.facebook.com`)
    ou Direct (apps in-app). Proponha `url_tags` padrão no nível da conta/anúncio, ex.:
    `utm_source=meta&utm_medium=paid_social&utm_campaign={{campaign.name}}&utm_content={{ad.name}}`
    e confira que `utm_medium` casa com a regra de `Paid Social` em `fct_sessions`.
  - `host` fora de `site_scope = website`/`landing_pages` (staging, domínio antigo) = achado.
  - `is_whatsapp` → anúncio click-to-WhatsApp: o lead não passa pelo site; atribuição
    depende do código de referência (`attribution_carrier` em `hubspot-funnel.yaml`).
- Cruze com BigQuery:
  ```sql
  SELECT landing_hostname, landing_page_path, source, medium, campaign, SUM(sessions) sessions, SUM(sessions_with_lead) leads
  FROM `PROJECT.growth_clean.rpt_landing_pages`
  WHERE session_date BETWEEN @start AND @end
    AND (REGEXP_CONTAINS(LOWER(source), r'facebook|instagram|meta|fb|ig') OR channel = 'Paid Social')
  GROUP BY 1, 2, 3, 4, 5 ORDER BY sessions DESC
  ```
  e as sessões com `referrer_host` `l.facebook.com`/`lm.instagram.com` sem UTM.

## 2. Números: Meta × GA4 × HubSpot
- `get_insights` (level `campaign`, mesma janela, `time_increment` "all_days"):
  `inline_link_clicks`, `actions` → `landing_page_view`, `lead`, `onsite_conversion.lead_grouped`,
  `offsite_conversion.fb_pixel_lead`.
- Espera-se: link clicks ≥ landing_page_view ≈ sessões Paid Social (±20%). Muito
  abaixo = página lenta/redirect ou UTM ausente; acima = pixel duplicado.
- Leads do pixel × `generate_lead` Paid Social × contatos HubSpot com fonte Paid Social.

## 3. Pixel / Conversions API
- `get_pixel_stats` com `aggregation`:
  - `event`: eventos recebidos; mapeie com `platform_events` de `event-taxonomy.yaml`
    (Lead ↔ generate_lead, Contact ↔ ctw_click). Eventos customizados soltos = sujeira.
  - `host`: quais hostnames disparam o pixel (LPs, subdomínios, staging).
  - `event_source`: navegador × servidor (CAPI). Se ambos enviam o mesmo evento, o
    `event_id` precisa bater (confira `eid` no `site-tagging-qa`); senão, conta em dobro.
  - `match_keys`: qualidade de correspondência (email/telefone hash, fbp, fbc).
- Pixel instalado por plugin do WordPress **e** pelo GTM: veja `gtm-container-audit`.

## 4. Lead Ads (formulários instantâneos)
- `list_leadgen_forms` por Page: `status`, `leads_count`, perguntas (tem campo que
  identifique campanha/produto?), `thank_you_page.website_url` (tem UTM?).
- Compare `leads_count` (delta na janela) × contatos criados no HubSpot pela
  integração do Meta (`hubspot-search-objects`, `hs_analytics_source = PAID_SOCIAL`,
  `hs_analytics_source_data_1` / `recent_conversion_event_name`). Gap = sincronização
  quebrada ou form sem mapeamento (entrada `meta-lead-ads` de `hubspot-funnel.yaml`).
- Lifecycle/owner desses contatos: siga `hubspot-form-routing`.

## 5. Entregável
Anúncios sem UTM (IDs, gasto), destinos fora do escopo, reconciliação cliques →
sessões → leads → contatos, problemas de pixel/CAPI e de Lead Ads, com correções.

## Escrita (somente com `meta-ads-official` carregado e "ok" explícito)
Só `url_tags`/destinos e itens PAUSED. Não ative anúncios nem altere orçamento sem
pedido explícito; liste IDs alterados.
