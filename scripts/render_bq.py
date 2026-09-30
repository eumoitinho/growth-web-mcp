#!/usr/bin/env python3
"""Renders bigquery/sql/*.sql templates with values from config/*.yaml.

Placeholders:
  {{project}} {{ga4_project}} {{ga4_dataset}} {{clean}} {{lookback_days}}
  {{site_scope(EXPR)}}      CASE expression classifying a hostname EXPR
                            with the rules of config/site-scope.yaml
  {{event_taxonomy_rows}}   rows of dim_event_taxonomy from
                            config/event-taxonomy.yaml

Usage:
  python scripts/render_bq.py --project your-gcp-project [--ga4-project other-project] \
      [--ga4-dataset analytics_123] \
      [--clean growth_clean] [--lookback-days 180] [--out bigquery/build]
"""

import argparse
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent


def sql_str(value) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def site_scope_case(expr: str, scope_cfg: dict) -> str:
    whens = []
    for rule in scope_cfg["hostnames"]:
        pattern = rule["pattern"]
        re.compile(pattern)  # fail fast on invalid regex
        if "'" in pattern:
            sys.exit(f"site-scope pattern must not contain a single quote: {pattern}")
        whens.append(f"WHEN REGEXP_CONTAINS(LOWER({expr}), r'{pattern}') THEN {sql_str(rule['scope'])}")
    default = sql_str(scope_cfg.get("default_scope", "unknown"))
    return "CASE " + " ".join(whens) + f" ELSE {default} END"


def taxonomy_rows(tax: dict) -> str:
    rows: dict[str, tuple] = {}

    def add(event_name, canonical, status, stage, conversion, note):
        if event_name in rows:
            sys.exit(f"event-taxonomy: '{event_name}' is listed more than once")
        rows[event_name] = (event_name, canonical, status, stage, bool(conversion), note)

    canonical = tax.get("canonical", {})
    for name, spec in canonical.items():
        spec = spec or {}
        add(name, name, "canonical", spec.get("stage"), spec.get("conversion", False), spec.get("description"))
    for name in tax.get("auto", []):
        add(name, name, "auto", "auto", False, "GA4 automatic / enhanced measurement")
    for name, note in (tax.get("review") or {}).items():
        add(name, name, "review", None, False, " ".join(str(note).split()))
    for target, aliases in (tax.get("aliases") or {}).items():
        if target not in canonical:
            sys.exit(f"event-taxonomy: alias target '{target}' is not a canonical event")
        spec = canonical[target] or {}
        for alias in aliases:
            add(alias, target, "alias", spec.get("stage"), spec.get("conversion", False), f"alias of {target}")
    for name in tax.get("noise", []):
        add(name, name, "noise", None, False, "ignored")

    lines = [
        "  (" + ", ".join([sql_str(n), sql_str(c), sql_str(s), sql_str(st), "TRUE" if conv else "FALSE", sql_str(note)]) + ")"
        for n, c, s, st, conv, note in rows.values()
    ]
    return ",\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--ga4-project", help="project holding the GA4 export; default: primary property export_project, else --project")
    parser.add_argument("--ga4-dataset", help="default: primary property export_dataset in config/site-scope.yaml")
    parser.add_argument("--clean", default="growth_clean")
    parser.add_argument("--lookback-days", type=int, default=180)
    parser.add_argument("--out", default=str(ROOT / "bigquery" / "build"))
    args = parser.parse_args()

    scope_cfg = yaml.safe_load((ROOT / "config" / "site-scope.yaml").read_text())
    tax = yaml.safe_load((ROOT / "config" / "event-taxonomy.yaml").read_text())

    props = scope_cfg["ga4"]["properties"]
    primary = next((p for p in props if p.get("primary")), props[0])
    ga4_dataset = args.ga4_dataset or primary["export_dataset"]
    ga4_project = args.ga4_project or primary.get("export_project") or args.project

    values = {
        "project": args.project,
        "ga4_project": ga4_project,
        "ga4_dataset": ga4_dataset,
        "clean": args.clean,
        "lookback_days": str(args.lookback_days),
        "event_taxonomy_rows": taxonomy_rows(tax),
    }

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for template in sorted((ROOT / "bigquery" / "sql").glob("*.sql")):
        sql = template.read_text()
        sql = re.sub(r"\{\{site_scope\((.+?)\)\}\}", lambda m: site_scope_case(m.group(1), scope_cfg), sql)
        sql = re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], sql)
        (out / template.name).write_text(sql)
        print(out / template.name)


if __name__ == "__main__":
    main()
