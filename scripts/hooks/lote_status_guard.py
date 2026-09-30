#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write|Bash): the agent cannot approve its own lote.

Blocks writes that would set "Status: aprovado" in docs/remediation or touch
.claude/lote-ativo. Approval comes only from the human prompt (lote_approve.py).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lote_common import emit, read_event  # noqa: E402

APPROVED = re.compile(r"Status:\*\*\s*aprovado|Status:\\\*\\\*\s*aprovado", re.IGNORECASE)


def deny(reason):
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": reason}})


def main():
    event = read_event()
    tool = event.get("tool_name")
    ti = event.get("tool_input") or {}
    if tool in ("Edit", "Write"):
        path = ti.get("file_path") or ""
        text = ti.get("new_string") or ti.get("content") or ""
        if path.endswith(os.path.join(".claude", "lote-ativo")):
            deny("O lote ativo é definido pela aprovação do usuário ('ok lote NN'), não pelo agente.")
        if "docs/remediation/" in path and APPROVED.search(text):
            deny("Só o usuário aprova um lote: peça 'ok lote NN' na conversa.")
    elif tool == "Bash":
        cmd = ti.get("command") or ""
        # writing to the file itself (> / >> / tee / cp / mv onto .claude/lote-ativo), not mentioning it
        if re.search(r"(>>?|\btee\b(\s+-a)?)\s*['\"]?\S*\.claude/lote-ativo\b|\b(cp|mv)\b.*\s['\"]?\S*\.claude/lote-ativo['\"]?\s*($|[;&|])", cmd):
            deny("O lote ativo é definido pela aprovação do usuário ('ok lote NN').")
        # sed/python/... setting the Status line of a lote doc (a commit message that
        # merely says "aprovado" is fine)
        writes_status = re.search(r"Status:\\?\*\\?\*\s*aprovado", cmd, re.IGNORECASE)
        flips_lote_doc = re.search(r"docs/remediation/lote-\d+", cmd) and re.search(r"proposto\W+aprovado", cmd, re.IGNORECASE)
        if "docs/remediation" in cmd and (writes_status or flips_lote_doc):
            deny("Só o usuário aprova um lote: peça 'ok lote NN' na conversa.")


if __name__ == "__main__":
    main()
