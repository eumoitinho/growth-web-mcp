#!/usr/bin/env python3
"""Tests for the remediation hooks: python3 scripts/hooks/test_hooks.py

Runs every hook as Claude Code does (JSON on stdin) against a temporary project
directory, so nothing in the repo changes.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
LOTE_DOC = "- **Status:** proposto\n- **Issue:** #1\n"


def run(script, event, root):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=root)
    out = subprocess.run([sys.executable, os.path.join(HERE, script)], input=json.dumps(event),
                         capture_output=True, text=True, env=env, check=True).stdout
    return json.loads(out) if out.strip() else None


def decision(out):
    return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision", "allow")


def main():
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, ".claude"))
    os.makedirs(os.path.join(root, "docs", "remediation"))
    with open(os.path.join(root, "docs", "remediation", "lote-01-teste.md"), "w") as fh:
        fh.write("# Lote 01\n\n" + LOTE_DOC)
    gtm = "mcp__gtm-write__gtm_tag"
    notes = {"name": "GA4 - generate_lead", "notes": "lote-01 · consumido por GA4"}
    cases = [
        # (hook, event, expected decision)
        ("lote_guard.py", {"tool_name": gtm, "tool_input": {"action": "list"}}, "allow"),
        ("lote_guard.py", {"tool_name": gtm, "tool_input": {"action": "create"}}, "deny"),  # sem lote ativo
        ("lote_approve.py", {"prompt": "pode seguir, ok lote 01"}, None),
        ("lote_guard.py", {"tool_name": gtm, "tool_input": {"action": "create", "createOrUpdateConfig": {"name": "x"}}}, "deny"),
        ("lote_guard.py", {"tool_name": gtm, "tool_input": {"action": "create", "createOrUpdateConfig": notes}}, "allow"),
        ("lote_guard.py", {"tool_name": "mcp__gtm-write__gtm_workspace",
                           "tool_input": {"action": "create", "createOrUpdateConfig": {"name": "teste"}}}, "deny"),
        ("lote_guard.py", {"tool_name": "mcp__hubspot-write__hubspot-list-objects", "tool_input": {}}, "allow"),
        ("lote_status_guard.py", {"tool_name": "Edit", "tool_input": {
            "file_path": "/x/docs/remediation/lote-02-ga4.md", "new_string": "- **Status:** aprovado"}}, "deny"),
        ("lote_status_guard.py", {"tool_name": "Edit", "tool_input": {
            "file_path": "/x/docs/remediation/lote-01-gtm.md", "new_string": "- **Status:** publicado"}}, "allow"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {"command": "echo 02 > .claude/lote-ativo"}}, "deny"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {"command": "echo 02 | tee -a /x/.claude/lote-ativo"}}, "deny"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {"command": "cp /tmp/a .claude/lote-ativo"}}, "deny"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {"command": "printf '.claude/lote-ativo\\n' >> .gitignore"}}, "allow"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {"command": "cat .claude/lote-ativo"}}, "allow"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {"command": "sed -i s/proposto/aprovado/ docs/remediation/lote-02.md"}}, "deny"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {
            "command": "git add docs/remediation && git commit -m 'a aprovação só vem do usuário; lote aprovado > aplica'"}}, "allow"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {
            "command": "gh label create status:aprovado --description 'ver docs/remediation'"}}, "allow"),
        ("lote_status_guard.py", {"tool_name": "Bash", "tool_input": {
            "command": "python3 -c \"p='docs/remediation/lote-01-gtm.md'; s=open(p).read().replace('**Status:** proposto','**Status:** aprovado')\""}}, "deny"),
    ]
    failed = 0
    try:
        for script, event, want in cases:
            out = run(script, event, root)
            got = decision(out) if want else None
            ok = got == want
            failed += not ok
            label = event.get("tool_name") or event.get("prompt")
            print("%s %-22s %-40s -> %s" % ("ok  " if ok else "FAIL", script, str(label)[:40], got or "(aprovação)"))
        with open(os.path.join(root, "docs", "remediation", "lote-01-teste.md")) as fh:
            approved = "- **Status:** aprovado" in fh.read()
        print("%s status gravado pela aprovação do usuário" % ("ok  " if approved else "FAIL"))
        failed += not approved
    finally:
        shutil.rmtree(root)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
