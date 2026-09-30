# Remediação do inbound

O agente corrige o tracking e a configuração em **lotes**. Cada lote tem um documento
nesta pasta (`lote-NN-<assunto>.md`) com inventário, mudanças, testes e rollback. O
humano aprova o lote **uma vez**, com as evidências na mão.

## Ciclo de um lote

1. **Diagnóstico** com os servidores de leitura. Cada achado cita a fonte: tool,
   parâmetros e IDs.
2. **Documento do lote**, com três listas: o que **fica**, o que **muda** e o que
   **sai**, com o motivo de cada item. Nada é removido sem motivo registrado.
3. **Aplicação isolada.** GTM: workspace `agent-<assunto>-<data>` e uma versão criada,
   ainda não publicada. Ads e GA4: somente as ações listadas no documento.
4. **Verificação automática.** O `site-browser` abre as páginas do lote com o preview
   do GTM e confere, pelas requests de rede e pelo `dataLayer`, que cada tag dispara
   quando deve e só quando deve. Os formulários nunca são enviados em produção.
5. **Aprovação**: um "ok" na conversa para o lote inteiro.
6. **Publicação** e registro da versão publicada no documento.
7. **Confirmação do efeito** em D+1 e D+7: Ads × HubSpot × GA4. Se piorar, o rollback
   é publicar de novo a versão anterior, anotada no documento.

## Hooks que garantem o processo (`.claude/settings.json`)

| Hook | Quando | O que faz |
|---|---|---|
| `lote_approve.py` | `UserPromptSubmit` | o **usuário** escreve `ok lote 01` → status aprovado, lote ativo (`.claude/lote-ativo`) e registro da aprovação no changelog |
| `lote_status_guard.py` | antes de `Edit` / `Write` / `Bash` | o agente não consegue se autoaprovar (gravar o status de aprovado ou escrever em `.claude/lote-ativo`) |
| `lote_guard.py` | antes de qualquer tool de escrita (`gtm-write`, `hubspot-write`, `meta-ads-official`, `ads-write`, `ga4-write`) | bloqueia mudança sem lote ativo aprovado. No GTM, exige `notes` com `lote-NN`, workspace `agent-loteNN-…` e versão `lote-NN …`. Leituras passam |
| `lote_log.py` | depois de cada tool de escrita | registra a mudança (ferramenta, ação, IDs, nome, notes, resposta) em `changes/lote-NN.jsonl`, que fica local por padrão |
| `lote_sync.py` | execução manual opcional | publica os registros na issue via `gh`; revise os dados antes de executar |

Status de um lote: `proposto` → aprovado (só pelo usuário) → `publicado` → `verificado`.
Testes dos hooks: `python3 scripts/hooks/test_hooks.py`.

Os hooks evitam erro de processo; não substituem permissão. A última barreira é a
permissão das service accounts: sem **Publish** no GTM, nada vai ao ar sem um humano.

## Padrão de documentação (vale para tudo que o agente cria ou altera)

- **GTM:** todo recurso novo ou alterado recebe `notes` com o que faz, quem consome e
  qual lote o criou (ex.: `lote-01 · dispara no generate_lead · consumido por Ads/Meta/LinkedIn`).
  O nome segue `<Plataforma> - <Evento>`, por exemplo `GA4 - generate_lead`.
- **Versões do GTM:** o nome é `lote-NN <assunto>` e a descrição traz o link do
  documento do lote.
- **Ads / GA4:** a ação ou o evento novo leva uma descrição com o lote; a mudança de
  primária/secundária fica registrada no documento.
- **Repo:** contratos em `config/*.yaml` atualizados no mesmo PR do lote.

## Política de remoção

Sai tudo o que não tem consumidor ou não tem dono:
- trigger sem tag, variável sem referência, template sem tag;
- tag cujo destino não existe mais (label de conversão removido, pixel antigo);
- tags duplicadas (dois eventos iguais para a mesma plataforma).

Antes de remover, o item é listado no documento do lote com o ID e o motivo. A
versão anterior do GTM continua disponível para rollback.

## Backlog

Crie lotes e issues próprios após configurar suas integrações. Não publique logs com dados de contas ou contatos.
