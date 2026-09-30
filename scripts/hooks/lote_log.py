#!/usr/bin/env python3
"""PostToolUse hook: every change made through a write server lands in the lote changelog.

Appends one JSON line to docs/remediation/changes/lote-<NN>.jsonl (versioned with
the lote PR): when, which tool/action, the resource IDs, the name and notes sent,
and a short slice of the response. Read-only calls are ignored.
"""

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lote_common import active_lote, changes_file, is_change, read_event  # noqa: E402

ID_KEYS = ("accountId", "containerId", "workspaceId", "tagId", "triggerId", "variableId",
           "templateId", "containerVersionId", "folderId", "objectType", "objectId", "formId")


def main():
    event = read_event()
    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if not is_change(tool_name, tool_input):
        return
    config = tool_input.get("createOrUpdateConfig") or {}
    response = event.get("tool_response")
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "tool": tool_name,
        "action": tool_input.get("action"),
        "ids": {k: tool_input[k] for k in ID_KEYS if k in tool_input},
        "name": config.get("name"),
        "notes": config.get("notes"),
        "response": json.dumps(response, ensure_ascii=False)[:500] if response is not None else None,
    }
    with open(changes_file(active_lote() or "sem-lote"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
