# Validação de jornadas e serviços

Este projeto distingue três evidências: teste do código, jornada em aplicação de referência e jornada nas integrações reais. Uma execução local aprovada **não comprova** a configuração da sua conta GA4, campanha ou CRM.

## Organização das mudanças

As branches são empilhadas e devem ser revisadas nesta ordem:

1. `test/service-contracts`: políticas, transporte MCP, testes de adapters e contratos dos serviços.
2. `feat/journey-reconciliation`: schemas, contratos, correlação, coleta HubSpot/BigQuery e relatórios.
3. `feat/browser-journey-runner`: execução Chromium, cenários de referência e retomada sem reenvio.
4. `ci/quality-and-live-validation`: CI, validações adicionais e operação.

Cada branch depende da anterior. Faça merge na mesma ordem; após integrar uma base, ajuste a base do PR dependente para `main`. Nenhuma branch implanta infraestrutura automaticamente.

## Executar os testes locais

Use ambientes separados: GA4/Meta dependem de MCP 1; o gateway FastMCP 4 e Google Ads dependem de MCP 2.

```bash
python3.12 -m venv .venv-qa
source .venv-qa/bin/activate
pip install -r requirements-test.txt -e servers/ga4
python -m playwright install chromium
python scripts/hooks/test_hooks.py
python -m pytest tests/unit tests/contracts tests/journeys tests/e2e \
  --cov=growth_qa --cov-branch --cov-fail-under=75 --cov-report=term-missing
npm test --prefix servers/gtm
npm test --prefix servers/hubspot
php tests/wordpress/test_abilities.php
```

Instale as dependências Node com `npm ci --prefix servers/gtm` e `npm ci --prefix servers/hubspot` antes da primeira execução.

```bash
python3.12 -m venv .venv-gateway
.venv-gateway/bin/pip install -e servers/gateway google-ads-mcp==0.0.4 pytest pytest-asyncio pytest-cov
.venv-gateway/bin/python -m pytest tests/gateway tests/ads
```

A cobertura mínima de 75% considera linhas e branches de `growth_qa`, não todo o repositório. A cobertura do gateway é reportada separadamente. O CI também executa PHP, Terraform e build das sete imagens. Esses checks não fazem deploy.

## O que os testes comprovam

| Camada | Evidência automatizada | Limite |
|---|---|---|
| GTM/HubSpot | políticas de acesso; protocolo HTTP/MCP real; rejeição de erros | permissões nas contas reais exigem execução live |
| GA4 | paginação e nomes dos recursos Admin; saúde do wrapper | APIs mockadas nos testes unitários |
| Meta | erros, paginação, URLs de anúncios, parâmetros e tratamento de token de Page | não confirma recebimento ou atribuição real do Pixel/CAPI |
| Google Ads | modo IAM/OAuth e schema real do upstream instalado | não gera cliques reais nem conversões atribuídas |
| Gateway | identidade, domínio verificado, expiração/isolamento de sessões e log de erro | não percorre o login Google real |
| WordPress | parser e capability com funções de fronteira simuladas | instalação real do Adapter exige teste live |
| BigQuery | renderização, contratos e consulta parametrizada correlacionada | execução SQL e export dependem do seu projeto |
| Navegador | ações reais no Chromium, rede e dataLayer; falhas injetadas | o CRM/GA4 da aplicação de referência são simulados |

A aplicação de referência cobre orgânico, Google Ads, Meta Ads, consentimento negado, erro de formulário, reenvio, contato existente, retorno direto e navegação entre hosts. Os testes injetam duplicação e perda de campanha e exigem que o reconciliador reprove.

## Preparar homologação

1. Configure um site/backend de teste, propriedades e contas apropriadas, formulários e contatos sintéticos. Exclua esses contatos de automações comerciais.
2. Copie `config/journeys.example.yaml`, `config/browser.example.yaml`, `config/collectors.example.yaml` e `config/services.example.yaml` para arquivos `*.local.yaml`, ignorados pelo Git.
3. Ajuste seletores, domínios autorizados, contas, formulários, propriedades de atribuição, lifecycle, owner e deadlines. Cenários como contato existente e cross-domain precisam ser preparados no seu ambiente.
4. Instale as views atualizadas do BigQuery: `test_run_id`, `submission_id` e `event_id` agora são preservados em `stg_events` e `fct_conversions`. O coletor usa `stg_events`, para não esconder duplicações via agregação.
5. Configure credenciais de leitura no ambiente (`QA_HUBSPOT_TOKEN`, ADC do Google) e endereços sintéticos em `QA_TEST_EMAIL` e `QA_EXISTING_CONTACT_EMAIL`. Nunca os versione.

### Instrumentação necessária no site/backend

O runner acrescenta `test_run_id` à URL inicial. **Seu aplicativo precisa propagá-lo**; o runner não altera eventos para fazê-los passar.

- Preserve esse ID na navegação autorizada e nos campos de teste do formulário.
- Gere `submission_id` no início de uma tentativa lógica e reutilize-o em retries. O backend deve implementar idempotência; o runner apenas verifica o resultado.
- Após sucesso, envie os IDs como parâmetros do `generate_lead` e como propriedades/campos personalizados no HubSpot. Cadastre previamente essas propriedades no portal de teste.
- Preserve first touch e last touch segundo sua política. Não reutilize e-mail ou telefone como identificador de analytics.
- Para deduplicação browser/server, propague o mesmo `event_id` e forneça evidência independente do destino. Receber duas requests não prova deduplicação na plataforma.

Exemplo de evento emitido **pelo aplicativo** após confirmação do backend:

```javascript
dataLayer.push({
  event: 'generate_lead',
  test_run_id: testRunId,
  submission_id: submissionId,
  form_id: 'demo',
  hubspot_form_id: testFormId,
  lead_type: 'demo',
  utm_source: attribution.source,
  utm_medium: attribution.medium,
  utm_campaign: attribution.campaign
});
```

As regras de consentimento são específicas da instalação. O exemplo de consentimento negado exige ausência de `generate_lead` no navegador, rede e GA4, mas permite a submissão solicitada ao CRM. Adapte ao modo de consentimento do seu site, incluindo pings sem cookies quando aplicável. O runner não contorna bloqueadores nem injeta consentimento.

### Rodar e retomar uma jornada

```bash
python -m growth_qa.pipeline \
  --suite config/journeys.local.yaml \
  --journey google-ads-demo \
  --settings config/browser.local.yaml \
  --collectors config/collectors.local.yaml \
  --out artifacts/google-ads-demo-001 \
  --allow-submissions
```

O runner só aceita `environment: test` e origens explicitamente autorizadas. A flag confirma o envio de formulários ao ambiente de teste. Inclua na allowlist os hosts de assets e coleta usados por ele. A execução utiliza um contexto novo de navegador por jornada.

A captura `network` observa o **envio** de payloads GA4 (`en` e parâmetros `ep.*`). Ela não representa aceitação pela API. A evidência `ga4` vem de uma consulta independente ao BigQuery, e a evidência `hubspot` vem de submissões e contatos consultados na API.

O export diário do GA4 pode ainda não conter o evento. Reexecute somente a coleta:

```bash
python -m growth_qa.pipeline \
  --suite config/journeys.local.yaml \
  --collectors config/collectors.local.yaml \
  --out artifacts/google-ads-demo-001 --resume
```

A retomada não abre o navegador nem reenvia formulários. Cada fonte substitui seu snapshot anterior, evitando contar a mesma consulta duas vezes. A paginação é limitada; respostas truncadas ou APIs indisponíveis produzem `ERROR`, não ausência de lead.

Os prazos são relativos ao início da jornada. Configure uma janela suficiente para ingestão e uma janela menor para confirmação imediata no CRM. A ausência só reprova após uma consulta realizada depois do prazo. Eventos proibidos precisam de uma janela completa de observação. Uma aprovação representa o snapshot consultado; eventos duplicados que chegarem depois exigem nova reconciliação.

### Estados e saídas

| Estado | Significado | Exit code |
|---|---|---|
| PASS | Contagem e campos conferem nas fontes consultadas | 0 |
| FAIL | Evidência contradiz o contrato | 1 |
| ERROR | Não foi possível obter evidência confiável | 1 |
| PENDING | Ainda dentro do prazo de ingestão | 2 |
| NOT_APPLICABLE | Etapa explicitamente excluída | 3 quando toda a jornada está excluída |

Cada execução gera `evidence.json`, `report.json`, `report.md` e `junit.xml`. O relatório contém contagens e motivos, sem copiar valores do contato. A evidência retém apenas campos permitidos; não inclui e-mail, telefone, nome, cookies ou resposta completa da API. Traces são opcionais e locais: podem conter dados da página e credenciais. O workflow live desativa traces.

```bash
python -m growth_qa.monitor --suite config/journeys.local.yaml \
  --reports artifacts --out artifacts/health.json
```

O agregador usa o último arquivo de relatório de cada jornada por horário de modificação. Jornadas não executadas aparecem como `NOT_TESTED`, não como sucesso. Para operação contínua, preserve uma pasta por execução, reconcilie após o prazo e use o exit code para seu sistema de alertas. Não há envio automático de mensagens a terceiros.

## Contratos dos nove endpoints MCP

```bash
python -m growth_qa.services --config config/services.local.yaml
```

Configure headers completos em variáveis: `QA_GOOGLE_AUTH_HEADER` para ID token/IAM, `QA_GOOGLE_ACCESS_HEADER` para access token/BigQuery, `QA_WP_AUTH_HEADER` para Basic Auth e `QA_GATEWAY_AUTH_HEADER` para OAuth do gateway. Eles não são intercambiáveis. Gere-os com sua identidade de teste autorizada.

O manifest cobre GA4, Ads, GTM, HubSpot, Meta, BigQuery, WordPress, navegador e gateway. Ele testa rejeição sem autenticação, descoberta de ferramentas, schemas e chamadas de leitura. Ajuste os nomes/argumentos ao `tools/list` da versão efetivamente instalada, especialmente WordPress e serviços gerenciados. Uma configuração ausente retorna `BLOCKED` e código diferente de zero. O contrato BigQuery usa `execute_sql_readonly` com `projectId` e `query`.

## CI e homologação no GitHub

`Quality` roda em pushes, PRs e diariamente após o workflow chegar à branch padrão. Não utiliza secrets; forks podem executar os testes. Inclui testes do navegador contra a aplicação de referência e builds dos containers.

`Test-environment journey` é manual e utiliza o environment `qa`. Configure:

- Variáveis `QA_BROWSER_SETTINGS`, `QA_COLLECTORS_CONFIG`, `QA_JOURNEY_SUITE`: conteúdo YAML dos seus arquivos locais.
- Variáveis `QA_WIF_PROVIDER` e `QA_SERVICE_ACCOUNT`: identidade federada Google com leitura do dataset de teste.
- Secrets `QA_HUBSPOT_TOKEN`, `QA_TEST_EMAIL`, `QA_EXISTING_CONTACT_EMAIL`.

Para retomar, informe `resume_run_id` de uma execução anterior. Evidências resumidas ficam em artifacts por sete dias; não forneça dados pessoais nos campos de atribuição. `PENDING` mantém a execução sem aprovação; não é mascarado como teste verde.

## Limites explícitos e próximos adapters

- Click IDs fictícios validam transporte/persistência, não atribuição real de campanhas. Referrer sintético valida a regra de origem, não uma visita orgânica observada no mecanismo de busca.
- Os contratos WhatsApp e Lead Ads aceitam evidência no schema comum, mas **não há coletor nativo de conversas ou de recebimento de leads individuais Meta nesta versão**. Implemente um adapter de webhook/log da sua integração; essas etapas permanecem pendentes/erro sem evidência, nunca são aprovadas por um simples clique.
- O coletor HubSpot verifica os campos configurados de contato e submissão. Histórico de inscrição em workflows, pipeline de deals e downstream de automações exigem adapters adicionais; a presença de um lifecycle não prova execução de workflow.
- O runner usa Chromium. Amplie o executor e a matriz para WebKit/Firefox e dispositivos quando essas jornadas forem relevantes.
- Os testes SQL locais validam renderização e contratos, não executam o dialeto BigQuery. Rode as consultas em dataset de teste para comprovar semântica e permissões reais.

Referências: [Playwright traces](https://playwright.dev/docs/trace-viewer), [GA4 export](https://support.google.com/analytics/answer/9358801), [BigQuery MCP read-only](https://docs.cloud.google.com/bigquery/docs/reference/mcp/tools_list/execute_sql_readonly).
