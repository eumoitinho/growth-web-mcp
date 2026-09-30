#!/usr/bin/env python3
"""PreToolUse hook: no change in GTM / HubSpot / Meta / Ads / GA4 outside an approved lote.

Blocks (permissionDecision=deny, with the reason fed back to Claude) when:
  * there is no active lote (.claude/lote-ativo) or its document is missing;
  * the lote status is not "aprovado" / "em aplicação";
  * a GTM tag/trigger/variable is created or updated without `notes` naming the lote;
  * a GTM workspace is created with a name outside `agent-lote<NN>-...`.
Read-only calls always pass.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lote_common import (active_lote, doc_field, emit, is_change, lote_doc,  # noqa: E402
                         read_event, server_and_tool, ALLOWED_STATUSES)


def deny(reason):
    emit({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }})


def main():
    event = read_event()
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if not is_change(tool_name, tool_input):
        return

    lote = active_lote()
    if not lote:
        deny("Mudança bloqueada: nenhum lote ativo. Crie/aprove o documento em docs/remediation/ "
             "e grave o número em .claude/lote-ativo (ex.: 01).")
    doc = lote_doc(lote)
    if not doc:
        deny("Mudança bloqueada: lote %s ativo, mas docs/remediation/lote-%s-*.md não existe." % (lote, lote))
    status = (doc_field(doc, "Status") or "").lower()
    if status not in ALLOWED_STATUSES:
        deny("Mudança bloqueada: lote %s está com status '%s'. Só aplica com 'aprovado' "
             "(depois do ok humano) — atualize a linha '- **Status:**' do documento." % (lote, status or "?"))

    server, tool = server_and_tool(tool_name)
    if server == "gtm-write":
        action = tool_input.get("action")
        config = tool_input.get("createOrUpdateConfig") or {}
        tag = "lote-%s" % lote
        if tool in ("gtm_tag", "gtm_trigger", "gtm_variable") and action in ("create", "update"):
            if tag not in (config.get("notes") or ""):
                deny("Mudança bloqueada: %s %s sem documentação. Inclua em createOrUpdateConfig.notes "
                     "o que o recurso faz, quem consome e '%s'." % (tool, action, tag))
        if tool == "gtm_workspace" and action == "create":
            name = config.get("name") or ""
            if not name.startswith("agent-lote%s" % lote):
                deny("Workspace deve se chamar 'agent-lote%s-<assunto>-<data>' (recebido: '%s')." % (lote, name))
        if tool == "gtm_workspace" and action == "createVersion":
            name = config.get("name") or ""
            if not name.startswith(tag):
                deny("Versão deve se chamar '%s <assunto>' e a descrição deve apontar o documento do lote." % tag)


if __name__ == "__main__":
    main()
