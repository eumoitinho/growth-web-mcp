---
name: site-tagging-qa
description: Verifica no navegador (Chrome headless via site-browser) o que uma página realmente envia - carregamento do GTM, hits do GA4 (collect), conversões do Ads, dataLayer, cookies/UTMs, formulários e botões de WhatsApp. Use para confirmar hipóteses de tagueamento ou validar o site Next.js antes de ir ao ar.
---

# QA de tagueamento no navegador

Ferramentas do `site-browser` (Chrome DevTools MCP). **Nunca envie formulário real
em produção.**

## Roteiro por URL
1. `new_page` com a URL + UTMs de teste:
   `?utm_source=agent_qa&utm_medium=qa&utm_campaign=tagging_qa` (fácil de filtrar
   depois; esses hits ficam no GA4 — avise o usuário).
2. `list_network_requests` e filtre:
   - `googletagmanager.com/gtm.js?id=` → quais containers carregam (quantos?).
   - `googletagmanager.com/gtag/js?id=` → gtag direto do tema/plugin WordPress
     *além* do GTM = duplicidade clássica.
   - `/g/collect` ou `region1.google-analytics.com/g/collect` → hits GA4: leia
     `tid` (measurement ID), `en` (evento), `ep.*` (parâmetros), `dl` (URL).
   - `googleads.g.doubleclick.net`, `google.com/ccm/collect` → Ads / conversões.
   - `js.hs-scripts.com`, `track.hubspot.com`, `forms.hubspot.com`, `api.hsforms.com`.
   - `connect.facebook.net/.../fbevents.js` e `facebook.com/tr?id=` → pixel Meta:
     `id` (pixel), `ev` (evento), `eid` (event_id, necessário para deduplicar com a
     Conversions API). Pixel instalado duas vezes (plugin + GTM) = eventos em dobro.
   Use `get_network_request` para ver o payload completo.
3. `evaluate_script`:
   ```js
   () => ({ dataLayer: (window.dataLayer || []).map(e => e.event || Object.keys(e)[0]),
            gtm: Object.keys(window.google_tag_manager || {}),
            hubspotutk: document.cookie.match(/hubspotutk=([^;]+)/)?.[1] ?? null,
            ga: document.cookie.match(/_ga=([^;]+)/)?.[1] ?? null })
   ```
4. Consentimento: com banner, compare requests antes e depois de aceitar (`click`).
5. Formulário: `fill_form` com dados fictícios de QA e **pare antes do submit** em
   produção; inspecione o form (action, campos ocultos preenchidos com UTMs?, script
   que monta o payload da Forms API e se inclui `hutk`). Em staging pode submeter e
   então verificar `generate_lead` no collect.
6. WhatsApp: `take_snapshot`, encontre links `wa.me` / `api.whatsapp.com`, confira
   `text=` (código de referência?) e se o clique gera `ctw_click` (clique com o
   evento de rede observado — o link abre nova aba; aceite).
7. Navegação entre site ↔ LP ↔ blog: o `_ga`/sessão se mantém? (cross-domain/linker `_gl`).

## Origem do que você viu (wordpress)
Achou tag duplicada, pixel extra ou formulário sem `hutk`? Descubra quem injeta:
- `growth/list-tracking-snippets` (`path` da URL testada): IDs no HTML servido e IDs
  configurados em plugins de header/footer, GTM4WP e HubSpot.
- `growth/list-active-plugins`: plugin responsável (Site Kit, GTM4WP, PixelYourSite, HubSpot…).
- `growth/list-forms`: se o form é embed HubSpot, plugin (CF7/WPForms/Gravity) ou código
  próprio chamando a Forms API (arquivo + linha).
As abilities são expostas pelo MCP Adapter por meta-tools (descobrir → executar ability).

## Entregável
Por URL: containers/IDs carregados, eventos enviados (nome + parâmetros-chave),
divergências da taxonomia, duplicidades, problemas de UTM/hutk/consent, prints
(`take_screenshot`) quando ajudarem.
