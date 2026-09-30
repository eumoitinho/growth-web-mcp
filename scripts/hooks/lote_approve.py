#!/usr/bin/env python3
"""UserPromptSubmit hook: the human approves a lote by typing "ok lote 01".

Only a prompt typed by the person reaches this hook, so this is the one path
that sets "- **Status:** aprovado" (lote_status_guard.py blocks the agent from
writing it). It also marks the lote as active and records the approval in the
lote changelog.
"""

import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lote_common import ACTIVE_FILE, changes_file, emit, lote_doc, read_event  # noqa: E402

APPROVAL = re.compile(r"\b(?:ok|aprovo|aprovado)\s+(?:o\s+)?lote\s*0*(\d{1,2})\b", re.IGNORECASE)


def main():
    event = read_event()
    prompt = event.get("prompt") or ""
    m = APPROVAL.search(prompt)
    if not m:
        return
    lote = m.group(1).zfill(2)
    doc = lote_doc(lote)
    if not doc:
        emit({"systemMessage": "Aprovação ignorada: docs/remediation/lote-%s-*.md não existe." % lote})
    with open(doc, encoding="utf-8") as fh:
        text = fh.read()
    text, n = re.subn(r"^(\s*-\s*\*\*Status:\*\*).*$", r"\1 aprovado", text, count=1, flags=re.MULTILINE)
    if not n:
        emit({"systemMessage": "Aprovação ignorada: o documento do lote %s não tem a linha '- **Status:**'." % lote})
    with open(doc, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.makedirs(os.path.dirname(ACTIVE_FILE), exist_ok=True)
    with open(ACTIVE_FILE, "w") as fh:
        fh.write(lote + "\n")
    with open(changes_file(lote), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "tool": "user", "action": "approve", "ids": {}, "name": "lote-%s aprovado" % lote,
            "notes": prompt[:300], "response": None}, ensure_ascii=False) + "\n")
    emit({
        "systemMessage": "Lote %s aprovado e ativo." % lote,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "O usuário aprovou o lote %s agora (status gravado pelo hook). "
                                 "Pode aplicar as mudanças listadas em %s." % (lote, os.path.relpath(doc)),
        },
    })


if __name__ == "__main__":
    main()
