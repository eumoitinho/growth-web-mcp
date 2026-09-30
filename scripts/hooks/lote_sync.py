#!/usr/bin/env python3
"""Stop hook: new changelog lines of the active lote become a comment on its GitHub issue.

Reads docs/remediation/changes/lote-<NN>.jsonl, posts the lines not yet synced
(offset kept in .claude/lote-sync-<NN>, local) as one markdown table on the issue
named in the lote document ("- **Issue:** #N"), via `gh`. Never blocks: failures
become a warning shown to the user.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lote_common import ROOT, active_lote, changes_file, doc_field, emit, lote_doc  # noqa: E402


def main():
    lote = active_lote()
    if not lote:
        return
    path = changes_file(lote)
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        lines = [l for l in fh.read().splitlines() if l.strip()]
    marker = os.path.join(ROOT, ".claude", "lote-sync-%s" % lote)
    done = int(open(marker).read().strip() or 0) if os.path.exists(marker) else 0
    new = lines[done:]
    if not new:
        return

    doc = lote_doc(lote)
    issue = (doc_field(doc, "Issue") or "").lstrip("#") if doc else ""
    if not issue.isdigit():
        emit({"systemMessage": "lote %s: %d mudança(s) registradas, mas o documento não tem '- **Issue:** #N'." % (lote, len(new))})

    rows = ["| quando (UTC) | ferramenta | ação | IDs | nome |", "|---|---|---|---|---|"]
    for raw in new:
        e = json.loads(raw)
        ids = ", ".join("%s=%s" % kv for kv in (e.get("ids") or {}).items())
        rows.append("| %s | `%s` | %s | %s | %s |" % (e.get("ts"), e.get("tool"), e.get("action") or "",
                                                     ids, (e.get("name") or "").replace("|", "/")))
    body = "Mudanças aplicadas (registro automático do hook, `docs/remediation/changes/lote-%s.jsonl`):\n\n%s" % (
        lote, "\n".join(rows))
    result = subprocess.run(["gh", "issue", "comment", issue, "--body", body], cwd=ROOT,
                            capture_output=True, text=True)
    if result.returncode != 0:
        emit({"systemMessage": "lote %s: não consegui comentar na issue #%s (%s)." % (
            lote, issue, (result.stderr or "").strip()[:200])})
    with open(marker, "w") as fh:
        fh.write(str(len(lines)))
    emit({"systemMessage": "lote %s: %d mudança(s) comentadas na issue #%s." % (lote, len(new), issue)})


if __name__ == "__main__":
    main()
