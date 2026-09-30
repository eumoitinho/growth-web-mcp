#!/usr/bin/env bash
# Prints the env vars .mcp.json expects, from Terraform outputs.
#   scripts/write-env.sh > .env && set -a && source .env && set +a
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
terraform -chdir="$ROOT/infra/terraform" output -json mcp_urls | python3 -c '
import json, sys
for name, url in json.load(sys.stdin).items():
    key = name.upper().replace("-", "_")
    print("GROWTH_MCP_" + key + "_URL=" + url)
'
echo "GROWTH_GCP_PROJECT=$(terraform -chdir="$ROOT/infra/terraform" output -raw artifact_registry | cut -d/ -f2)"
