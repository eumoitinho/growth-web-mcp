# Contributing / Contribuindo / Contribuciones

## English

1. Open an issue for substantial changes so the scope can be discussed.
2. Fork the repository and create a branch for your change.
3. Keep changes focused, use fictional data and document configuration changes.
4. Run the relevant checks below and include their results in your pull request.
5. Keep `README.md`, `README.pt-BR.md` and `README.es.md` equivalent when changing shared documentation.

Contributions are licensed under Apache-2.0. Respect the [Code of Conduct](CODE_OF_CONDUCT.md). Do not commit credentials, Terraform state, operational logs or customer data.

## Português

1. Abra uma issue para discutir o escopo de mudanças maiores.
2. Faça um fork e crie uma branch para sua alteração.
3. Mantenha o escopo focado, use dados fictícios e documente mudanças de configuração.
4. Execute as verificações relevantes abaixo e informe os resultados no pull request.
5. Mantenha os três READMEs equivalentes ao alterar a documentação compartilhada.

As contribuições usam Apache-2.0. Respeite o [Código de Conduta](CODE_OF_CONDUCT.md). Não versione credenciais, estado Terraform, logs operacionais ou dados de clientes.

## Español

1. Abre una issue para discutir el alcance de cambios importantes.
2. Haz un fork y crea una rama para tu cambio.
3. Mantén el alcance enfocado, usa datos ficticios y documenta cambios de configuración.
4. Ejecuta las comprobaciones relevantes siguientes e incluye los resultados en el pull request.
5. Mantén equivalentes los tres READMEs al cambiar documentación compartida.

Las contribuciones usan Apache-2.0. Respeta el [Código de Conducta](CODE_OF_CONDUCT.md). No incluyas credenciales, estado de Terraform, registros operativos ni datos de clientes.

## Development checks

Python ≥ 3.11, Node.js ≥ 22, Terraform ≥ 1.6.

```bash
python3 scripts/hooks/test_hooks.py
# For each changed TypeScript server:
(cd servers/gtm && npm ci && npm run build)
(cd servers/hubspot && npm ci && npm run build)
# For infrastructure changes (no deployment):
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
# For data contract changes, with PyYAML installed:
python3 scripts/render_bq.py --project example-project
```

Live integration checks require your own accounts. Explain which checks were not run and why.

## Journey and integration validation

See [docs/validation.md](docs/validation.md) for the complete test matrix, separate MCP 1/2 environments, coverage checks and test-account setup. Never use a production form to run synthetic tests.
