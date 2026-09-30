"""Shared helpers for the remediation hooks (.claude/settings.json).

Which lote is active: the file `.claude/lote-ativo` (local, not versioned)
holds its number, e.g. `01`. The lote document `docs/remediation/lote-01-*.md`
carries the status and the GitHub issue in two header lines:

    - **Status:** aprovado
    - **Issue:** #12

Kept compatible with the macOS system python3 (3.9).
"""

import glob
import json
import os
import re
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ACTIVE_FILE = os.path.join(ROOT, ".claude", "lote-ativo")
CHANGES_DIR = os.path.join(ROOT, "docs", "remediation", "changes")

# Actions that only read, per write server. Anything else is a change.
READ_ACTIONS = {"get", "list", "live", "getStatus", "get_status"}
READ_TOOL_WORDS = ("get", "list", "search", "read", "insights", "describe")
ALLOWED_STATUSES = {"aprovado", "em aplicação", "em aplicacao"}


def read_event():
    return json.load(sys.stdin)


def server_and_tool(tool_name):
    # mcp__<server>__<tool>
    parts = tool_name.split("__", 2)
    return (parts[1], parts[2]) if len(parts) == 3 else ("", tool_name)


def is_change(tool_name, tool_input):
    server, tool = server_and_tool(tool_name)
    action = (tool_input or {}).get("action")
    if server in ("gtm-write", "ga4-write", "ads-write") and action:
        return action not in READ_ACTIONS
    # hubspot-list-objects, get_ad_accounts, ...: a read verb in the first two words.
    words = re.split(r"[-_]", tool.lower())[:2]
    return not any(w in READ_TOOL_WORDS for w in words)


def active_lote():
    try:
        with open(ACTIVE_FILE, encoding="utf-8") as fh:
            value = fh.read().strip()
    except OSError:
        return None
    return value.zfill(2) if value.isdigit() else None


def lote_doc(lote):
    matches = sorted(glob.glob(os.path.join(ROOT, "docs", "remediation", "lote-%s-*.md" % lote)))
    return matches[0] if matches else None


def doc_field(path, field):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^\s*-\s*\*\*%s:\*\*\s*(.+?)\.?\s*$" % re.escape(field), line)
            if m:
                return m.group(1).strip()
    return None


def changes_file(lote):
    os.makedirs(CHANGES_DIR, exist_ok=True)
    return os.path.join(CHANGES_DIR, "lote-%s.jsonl" % lote)


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.exit(0)
