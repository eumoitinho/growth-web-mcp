---
name: site-performance
description: Mede e explica a performance do site (Core Web Vitals de campo via CrUX e de laboratório via Lighthouse/trace), com foco no custo de tags e scripts de terceiros. Use para "o site é lento", "otimizar WordPress", "metas de performance do Next.js".
---

# Performance do site

## 1. Páginas
As `key_urls` de `config/site-scope.yaml` + top landing pages de
`rpt_landing_pages` (por sessões, últimos 28 dias). Mobile primeiro.

## 2. Medir (site-browser)
- `lighthouse_audit` (mobile) por URL: performance, SEO, acessibilidade, boas práticas.
- `emulate` (CPU 4x, rede "Slow 4G") → `performance_start_trace` com reload →
  `performance_stop_trace` → `performance_analyze_insight` para LCP, INP, CLS,
  render-blocking, third-parties. O trace já traz dados de campo do CrUX quando a
  URL tem volume.
- `list_network_requests`: peso e quantidade por domínio de terceiro (GTM, pixels,
  chat widgets, fontes, plugins WordPress).

## 3. Atribuir o custo às tags
Cruze os terceiros pesados com o inventário do `gtm-container-audit`: quais tags
custam mais e se ainda são usadas. Custom HTML síncrono e múltiplos pixels são os
suspeitos habituais.

## 4. Entregável
Tabela por URL (LCP, INP, CLS campo × lab, peso JS, nº requests de terceiros), top 5
causas com ganho estimado, e orçamento de performance/tag para o Next.js (ex.:
GTM carregado após interação para tags não essenciais, `next/script` com
`strategy="afterInteractive"`/`lazyOnload`, sem gtag duplicado).
