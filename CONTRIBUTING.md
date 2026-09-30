# Contribuindo

Abra uma issue ou pull request em https://github.com/eumoitinho/growth-web-mcp.
Explique o problema, a mudança e como ela foi validada.

Use Python 3.11+ e Node.js 22+. Execute `python3 scripts/hooks/test_hooks.py`.
Nos servidores TypeScript alterados, execute `npm ci` e `npm run build`.
Valide alterações de infraestrutura com `terraform fmt -check` e `terraform validate`.

Use apenas dados fictícios em exemplos e testes. Credenciais, estados Terraform,
logs operacionais e dados de clientes devem permanecer fora do Git.
As contribuições são disponibilizadas sob Apache-2.0, como o projeto.
