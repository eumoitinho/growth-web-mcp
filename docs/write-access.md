# Acesso de escrita

Leitura é o padrão. Escrita é possível para **GTM** e **HubSpot**, como um segundo
conjunto de serviços isolado do primeiro:

|                     | Leitura (`gtm`, `hubspot`)      | Escrita (`gtm-write`, `hubspot-write`)          |
|---------------------|---------------------------------|-------------------------------------------------|
| Cloud Run           | `growth-mcp-gtm`, `-hubspot`    | `growth-mcp-gtm-write`, `-hubspot-write`        |
| Identidade Google   | `mcp-google-reader` (Read)      | `mcp-gtm-writer` (Edit/Approve, sem Publish)    |
| Token HubSpot       | app privado só leitura          | **outro** app privado, só os escopos de escrita necessários |
| Quem invoca         | `invokers` + SA do agente       | `write_invokers` (lista curta, sem o agente automático) |
| No `.mcp.json`      | sim                             | não — `.mcp.write.example.json`, carregado explicitamente |

Assim o agente de análise nunca escreve por acidente, e dá para revogar escrita
sem tocar na leitura.

## Ligando

`infra/terraform/terraform.tfvars`:

```hcl
enable_write            = true
write_invokers          = ["user:maintainer@example.com"]
gtm_write_allow_delete  = false   # remover tags/triggers/variáveis
gtm_write_allow_publish = false   # publicar = ir ao ar. Recomendo manter false.
hubspot_write_tools     = ["hubspot-batch-update-objects", "hubspot-create-property", "hubspot-update-property"]
```

`scripts/bootstrap.sh` (ou `terraform apply`) cria os serviços e pede o token de
escrita do HubSpot (`hubspot-private-app-token-write`). Depois:

- **GTM**: adicione `mcp-gtm-writer@...` no container com permissão **Edit** (mudanças
  em workspace) ou **Approve** (também criar versões — necessário para
  `createVersion`). **Publish** só se `gtm_write_allow_publish = true`.
- **HubSpot**: app privado "growth-mcp-write" com os escopos de escrita que as tools
  habilitadas precisam (ex.: `crm.objects.contacts.write`, `crm.schemas.contacts.write`).

Para usar numa sessão: `claude --mcp-config .mcp.write.example.json` (com
`GROWTH_MCP_GTM_WRITE_URL` / `GROWTH_MCP_HUBSPOT_WRITE_URL` no ambiente; o
`scripts/write-env.sh` já gera).

## O que cada modo permite

### GTM (`servers/gtm/src/policy.ts`)
- `read`: `get`, `list`, `live`, `latest`, `lookup`, `snippet`, `getStatus`, `entities`.
- `write`: + `create`, `update`, `revert`, `undelete`, `createVersion`, `quickPreview`,
  `sync`, `resolveConflict`, `moveEntitiesToFolder`.
- `+ GTM_ALLOW_DELETE`: `remove`. `+ GTM_ALLOW_PUBLISH`: `publish`, `setLatest`.
- Sempre só leitura: `gtm_account`, `gtm_user_permission`, `gtm_environment`,
  `gtm_container` (operações de administração).
- O escopo OAuth pedido acompanha o modo (`tagmanager.readonly` → `edit.containers`
  → `publish`), e a permissão da SA no GTM é o limite final.

### HubSpot (`servers/hubspot/src/server.ts`)
- `read`: 13 tools de leitura do upstream + forms, submissões, pipelines.
- `write`: + as tools de escrita do upstream listadas em `HUBSPOT_WRITE_TOOLS`
  (`batch-update-objects`, `batch-create-objects`, `batch-create-associations`,
  `create/update-property`, `create/update-engagement`).

Toda chamada de escrita é registrada nos logs do Cloud Run (`audit ...`), e o
`CLAUDE.md` obriga o agente a mostrar o diff e esperar confirmação.

## Meta

Escrita no Meta **não** passa por este repo: use o
[MCP oficial do Meta](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-mcp-server/ads-mcp-server-overview)
(`https://mcp.facebook.com/ads`, beta), já listado em `.mcp.write.example.json` como
`meta-ads-official`.

- Login com Meta Business OAuth **da pessoa**; você escolhe as contas de anúncio
  na autorização. O que a pessoa pode fazer é o papel dela no Business Manager
  (ex.: *Analyst* = só leitura; *Advertiser* = cria/edita).
- Tudo que for criado nasce **PAUSED**.
- Sem tokens para guardar nem serviço para hospedar; os logs de auditoria ficam no
  Business Manager (*Activity history*).

A separação continua: o agente/analistas usam `meta` (leitura, system user); quem
precisa editar campanhas carrega `meta-ads-official` na sessão.

## E GA4 / Google Ads?

Os servidores oficiais são só leitura: o do GA4 fixa o escopo
`analytics.readonly` e o do Ads (0.0.4) não tem ferramentas de mutate. Escrita aí
exigiria tools próprias (ex.: GA4 Admin — criar key events / custom dimensions /
filtros de dados com `analytics.edit`). Dá para adicionar no mesmo padrão
(`servers/ga4/growth_ga4/extra_tools.py` + serviço `ga4-write`), mas recomendo
esperar a leitura estar estável: a maior parte da limpeza do GA4 é feita no GTM e
na taxonomia, não na propriedade.
