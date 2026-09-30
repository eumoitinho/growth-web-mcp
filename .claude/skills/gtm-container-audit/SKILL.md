---
name: gtm-container-audit
description: Audita o container do Google Tag Manager - versão publicada, tags GA4/Ads/HubSpot/pixels, triggers, variáveis, consentimento, duplicidades e tags mortas. Use para "o que o GTM dispara?", "por que esse evento duplica?", "limpar o container", ou para desenhar o container do site Next.js.
---

# Auditoria do container GTM

Sempre audite a **versão publicada** (`gtm_version` action `live`), não o workspace:
é o que está no ar.

## 1. Inventário
- `gtm_account list` → `gtm_container list` → identifique o container de
  `config/site-scope.yaml` (`public_id`).
- `gtm_version live`: tags, triggers, variáveis e built-ins da versão publicada.
- `gtm_version_header list`: frequência de publicação, quem, quando.
- `gtm_workspace list` + `getStatus`: mudanças não publicadas esquecidas?

## 2. Classifique cada tag
| tag | tipo (GA4 config/event, Ads conversão/remarketing, HubSpot, pixel, HTML custom) | evento enviado | trigger | pausada? | consent |

Procure:
- Mais de uma tag de configuração GA4 / Google tag com o mesmo measurement ID →
  page_view duplicado.
- Measurement IDs diferentes do stream oficial (`list_data_streams` no `ga4`).
- Tags de evento GA4 cujo nome não está na taxonomia canônica.
- Triggers de "Form Submission" do GTM em formulários HubSpot/custom (disparam antes
  da validação) — lead deve vir de callback de sucesso / `dataLayer.push`.
- Custom HTML pesado ou de terceiros sem uso (impacto em performance).
- Tags sem trigger, pausadas há meses, ou triggers órfãos.
- Conversões do Google Ads: qual evento/URL dispara e se bate com `generate_lead`.
- Consent Mode: tags respeitam consentimento (`consentSettings`)?

## 3. Cruze com a realidade
- `wordpress` → `growth/list-tracking-snippets` e `growth/list-active-plugins`: tags
  instaladas **fora** do GTM (plugin, tema, header/footer). Tudo que estiver fora do
  container é candidato a migrar para ele ou remover.
- `site-tagging-qa` para confirmar no navegador o que realmente sai.
- `rpt_event_hygiene` para ver o volume de cada evento que a tag gera.

## 4. Entregável
Inventário + problemas priorizados + **container alvo** (lista de tags/triggers/
variáveis que deveriam existir), útil também para o site Next.js.

## Escrita (somente com `gtm-write` carregado e "ok" explícito)
1. `gtm_workspace create` com nome `agent-<assunto>-<AAAAMMDD>`.
2. Alterações mínimas; antes de cada `update`, `get` e reenvie o objeto completo.
3. `gtm_workspace getStatus` → mostre o diff. `createVersion` com notas.
4. Não publique. Entregue o link/ID da versão para um humano revisar e publicar.
