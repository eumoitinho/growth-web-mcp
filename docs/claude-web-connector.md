# Conector "Growth MCP" no claude.ai

Para a equipe de marketing usar os MCPs de leitura pelo claude.ai, sem terminal:
a pessoa clica em **Conectar**, entra com a conta Google `@example.com` e já pode
perguntar.

```
claude.ai ──MCP OAuth──▶ growth-mcp-gateway ──ID token (SA mcp-gateway)──▶ ga4 · google-ads · gtm · hubspot · meta · site-browser
                          (Google Sign-In,     ──Basic (Secret Manager)──▶ WordPress MCP Adapter
                           só @example.com)
```

- **Um URL público** (`growth-mcp-gateway`). Os servidores de leitura continuam
  privados: quem não tem IAM recebe `403`.
- **Quem entra:** contas Google verificadas nos domínios de `gateway_allowed_domains`
  (configure explicitamente o domínio da sua organização). A tela de consentimento *Internal* bloqueia contas de fora já
  no Google; o gateway confere o e-mail de novo em cada chamada.
- **Só leitura:** os servidores `-write` nunca passam pelo gateway.
- **Auditoria:** cada chamada vira uma linha JSON no Cloud Logging, com e-mail, tool,
  sucesso e duração (`jsonPayload.event="tool_call"`).
- **Nomes das tools:** `ga4_*`, `ads_*`, `meta_*`, `site_*`, `wp_*`; `gtm_*` e
  `hubspot-*` mantêm os nomes originais.
- **Regras para o Claude:** vão em `servers/gateway/growth_gateway/instructions.md`,
  que o claude.ai recebe ao conectar. É a versão curta do `CLAUDE.md` para quem não
  usa o repo.

## 1. OAuth do Google (uma vez, no console)

Projeto `your-gcp-project`:

1. **APIs & Services → OAuth consent screen**: tipo de usuário **Internal**, nome
   "Growth MCP", e-mail de suporte do time. Escopos: `openid` e `email`.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Tipo **Web application**, nome `mcp-gateway`.
   - *Authorized redirect URIs*: a saída `oauth_redirect_uri` do Terraform, que é
     `https://growth-mcp-gateway-<número do projeto>.southamerica-east1.run.app/auth/callback`.
3. Guarde o **Client ID**: ele vai em `gateway_oauth_client_id` no `terraform.tfvars`.
   O **Client secret** vai para o Secret Manager no passo 2.

## 2. Secrets e deploy

```bash
cd ~/growth-web-mcp
cat >> infra/terraform/terraform.tfvars <<'EOF'
enable_gateway          = true
gateway_oauth_client_id = "<client id>.apps.googleusercontent.com"
EOF

# cria só os secrets
terraform -chdir=infra/terraform apply -target=google_secret_manager_secret.gateway

# valores: client secret, duas chaves aleatórias e a credencial do WordPress
read -rs "S?Client secret do OAuth: "; echo
printf '%s' "$S" | gcloud secrets versions add gateway-google-oauth-client-secret --data-file=-; unset S
openssl rand -base64 48 | tr -d '\n' | gcloud secrets versions add gateway-jwt-signing-key --data-file=-
python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode(),end="")' \
  | gcloud secrets versions add gateway-storage-key --data-file=-
grep '^WP_MCP_BASIC_AUTH=' .env | cut -d= -f2- | tr -d '\n' \
  | gcloud secrets versions add wordpress-mcp-basic-auth --data-file=-

# build (inclui a imagem gateway) e apply completo
PROJECT_ID=your-gcp-project REGION=southamerica-east1 TAG="$(git rev-parse --short HEAD)" scripts/bootstrap.sh
terraform -chdir=infra/terraform output gateway
```

- Trocar a `gateway-jwt-signing-key` ou a `gateway-storage-key` desconecta todo mundo:
  cada pessoa clica em **Conectar** de novo.
- O `gateway-storage-key` precisa ser uma chave Fernet (32 bytes em base64 url-safe),
  como no comando acima.

## 3. Publicar no claude.ai (admin do Team)

1. **Admin settings → Connectors → Add custom connector**
2. Nome **Growth MCP**; URL = `connector_url` da saída do Terraform
   (`…run.app/mcp`). Deixe *OAuth Client ID/Secret* em branco: o gateway faz registro
   dinâmico.
3. Salvar. O conector aparece para todos da organização.

## 4. Para quem usa (texto para mandar à equipe)

> 1. No claude.ai, clique no seu nome → **Settings → Connectors**.
> 2. Em **Growth MCP**, clique em **Connect** e entre com seu e-mail @example.com.
> 3. Numa conversa nova, pergunte, por exemplo: *"Quantos leads o Google Ads trouxe
>    nos últimos 30 dias, por campanha?"* ou *"Quais formulários do site mais
>    receberam envios este mês no HubSpot?"*
>
> Se o Claude pedir permissão para usar uma ferramenta, clique em **Allow**.

## Operação

- **Logs:** `gcloud logging read 'resource.labels.service_name="growth-mcp-gateway" AND jsonPayload.event="tool_call"' --limit 50`
- **Tirar o acesso de alguém:** desativar a conta no Workspace resolve na próxima
  renovação de token (até 1 h). Para cortar todo mundo na hora, gire a
  `gateway-jwt-signing-key` e faça um novo deploy.
- **Escala:** 1 instância, com 80 chamadas simultâneas. O limite é de propósito:
  a sessão do navegador (`site_*`) de cada pessoa fica na memória dela.
- **Custo:** escala a zero quando ninguém usa. A primeira chamada depois de um
  tempo parado leva alguns segundos a mais.
