# WordPress → MCP (só leitura)

O agente enxerga o WordPress do site por dentro — **quem** injeta cada tag e
**como** cada formulário chega ao HubSpot — via o
[MCP Adapter oficial do WordPress](https://github.com/WordPress/mcp-adapter)
(Abilities API, WordPress 6.9+) mais as abilities deste diretório.

Não roda no Cloud Run: o Claude Code conecta direto em
`https://<site>/wp-json/mcp/mcp-adapter-default-server`.

## Abilities (`growth-abilities.php`, todas read-only)

| Ability | Retorna |
|---|---|
| `growth/list-active-plugins` | plugins ativos e mu-plugins (nome, versão, autor), tema, versão do WP |
| `growth/list-tracking-snippets` | para uma página do site: IDs GTM-/G-/AW-/pixel Meta/portal e forms HubSpot no HTML, hosts de scripts de terceiros, embed x Forms API, links de WhatsApp; IDs configurados em plugins de header/footer, GTM4WP e HubSpot (só IDs) |
| `growth/list-forms` | formulários CF7 / WPForms / Gravity, embeds HubSpot no conteúdo (URL + form GUID) e arquivos do tema/plugins que chamam a Forms API do HubSpot (arquivo + linha) |
| `growth/list-pages` | páginas publicadas: URL, template, modificação, forms HubSpot e links de WhatsApp |

Nenhuma ability devolve valores de opções, credenciais ou dados pessoais.
Só rodam para usuários com a capability `growth_read` (papel **Growth Agent**,
criado pelo próprio arquivo; administradores também recebem).

## Instalação (quem administra o WordPress)

1. WordPress **6.9+** (Painel → Atualizações).
2. Instalar e ativar o plugin **MCP Adapter** (zip da última release em
   github.com/WordPress/mcp-adapter/releases → Plugins → Adicionar novo → Enviar plugin).
3. Copiar `growth-abilities.php` para `wp-content/mu-plugins/` (SFTP ou
   gerenciador de arquivos da hospedagem; crie a pasta se não existir). mu-plugins
   não aparecem para desativar por engano e carregam sempre.
4. Criar o usuário `growth-agent` (Usuários → Adicionar novo), e-mail de grupo,
   papel **Growth Agent (read-only)**.
5. Logado como admin, editar esse usuário → **Senhas de aplicativo** → nome
   `growth-mcp` → **Adicionar**. Copie a senha (aparece uma vez).
6. Se houver plugin de segurança (Wordfence, iThemes, Cloudflare WAF), liberar
   `/wp-json/mcp/` e Application Passwords para esse usuário.

## Testar e conectar

```bash
export WP_MCP_BASIC_AUTH=$(printf '%s' 'growth-agent:SENHA DE APLICATIVO' | base64 -w0)
curl -s -X POST https://www.example.com/wp-json/mcp/mcp-adapter-default-server \
  -H "Authorization: Basic $WP_MCP_BASIC_AUTH" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Deve listar os meta-tools do adapter (descobrir / ver / executar abilities). O
`.mcp.json` já tem o servidor `wordpress`; basta `WP_MCP_BASIC_AUTH` no ambiente
e `WP_MCP_URL` com a URL do seu WordPress MCP Adapter.

## Remover

Apagar `wp-content/mu-plugins/growth-abilities.php`, revogar a senha de
aplicativo e desativar o MCP Adapter. Na migração para Next.js, este diretório
some junto com o WordPress.
