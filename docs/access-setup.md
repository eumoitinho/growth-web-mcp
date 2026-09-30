# Concedendo acesso

O Terraform cria as identidades; o acesso a cada produto é concedido **na interface
do produto**. É isso que mantém leitura e escrita separadas e auditáveis.
Pegue os e-mails com `terraform -chdir=infra/terraform output service_accounts`.

## Leitura (obrigatório)

### GA4 → `mcp-google-reader@<projeto>.iam.gserviceaccount.com`
Admin → *Property access management* (ou no nível da conta) → **+** → papel
**Viewer**. Repita para cada propriedade listada em `config/site-scope.yaml`.

Export para BigQuery: Admin → *Product links* → *BigQuery links* → export **diário**
(streaming é opcional) no mesmo projeto. O dataset fica `analytics_<property_id>`;
coloque em `ga4_export_dataset` no `terraform.tfvars` e no `site-scope.yaml`.

### Google Ads → `mcp-google-reader@...`
1. Na conta (ou MCC): Admin → *Access and security* → **+** → e-mail da service
   account → acesso **Read only**. (Acesso direto de service account; não precisa de
   delegação de domínio.)
2. Developer token: MCC → Admin → *API Center*. Nível **Explorer** ou **Basic** é
   suficiente para leitura. Salve no Secret Manager (o `bootstrap.sh` pergunta):
   `google-ads-developer-token`.
3. Se o acesso for via MCC, preencha `google_ads_login_customer_id`.

### Google Tag Manager → `mcp-google-reader@...`
Admin → *User management* (conta) → **+** → e-mail → permissão de conta **User**,
permissão de container **Read** nos containers do site/LPs.

### HubSpot → account service key de leitura
**Development → Keys → Account service keys → Create service key** (em portais
antigos que ainda têm, *Settings → Integrations → Private apps* funciona igual) →
**"growth-mcp-read"** com escopos:

```
crm.objects.contacts.read     crm.schemas.contacts.read
crm.objects.companies.read    crm.schemas.companies.read
crm.objects.deals.read        crm.schemas.deals.read
crm.objects.owners.read       tickets
forms                         automation
```

`forms` e `automation` não têm variante só-leitura no HubSpot; o servidor de leitura
não expõe nenhuma ferramenta que escreva neles. Salve a chave em
`hubspot-private-app-token-read` (nome do secret mantido por compatibilidade).

**Não use a Personal Access Key**: ela é do CLI de desenvolvedor, carrega todas as
permissões do seu usuário e não funciona como `Bearer` nas APIs de CRM.

### Meta → system user de leitura
1. Business Settings → *Users* → *System users* → **Add** → "growth-mcp-read",
   papel **Employee**.
2. *Assign assets*: contas de anúncio (**View performance**), pixels/datasets
   (**View**), Pages com Lead Ads (acesso a leads, se for auditar Lead Ads).
3. *Generate token* com um app do Business (tipo Business) e as permissões
   `ads_read`, `read_insights`, `business_management`, `pages_show_list`,
   `pages_read_engagement`, `leads_retrieval` (só para Lead Ads).
   Token de system user pode ser sem expiração; se escolher expiração de 60 dias,
   crie lembrete de rotação. Salve em `meta-system-user-token-read`.

O servidor nunca retorna dados pessoais de leads (só formulários e `leads_count`).

### Quem pode usar os servidores
`invokers` no `terraform.tfvars` (ex. `group:growth@example.com`). Recebem
`roles/run.invoker` nos serviços de leitura e acesso de leitura ao BigQuery
(`growth_clean` + export) e ao BigQuery MCP (`roles/mcp.toolUser`).

## Escrita (opcional)

Ver [`write-access.md`](write-access.md).
