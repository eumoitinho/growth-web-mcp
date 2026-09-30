#!/usr/bin/env bash
# headersHelper for .mcp.json. Claude Code runs it on every connection with
# CLAUDE_CODE_MCP_SERVER_NAME / CLAUDE_CODE_MCP_SERVER_URL set.
#
#   *.googleapis.com (Google-managed MCP, e.g. BigQuery) -> OAuth access token
#                                                           + quota project
#   anything else (our Cloud Run services, IAM-protected) -> identity token
#
# Set GROWTH_IMPERSONATE_SA=growth-agent@<project>.iam.gserviceaccount.com to
# act as the agent service account (tests exactly what it can reach; needs
# roles/iam.serviceAccountTokenCreator on it).
set -euo pipefail

url="${CLAUDE_CODE_MCP_SERVER_URL:-${1:-}}"
impersonate=()
if [[ -n "${GROWTH_IMPERSONATE_SA:-}" ]]; then
  impersonate=(--impersonate-service-account="$GROWTH_IMPERSONATE_SA")
fi

if [[ "$url" == https://*.googleapis.com/* ]]; then
  token="$(gcloud auth print-access-token "${impersonate[@]}" 2>/dev/null)"
  project="${GROWTH_GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
  printf '{"Authorization": "Bearer %s", "x-goog-user-project": "%s"}\n' "$token" "$project"
elif [[ ${#impersonate[@]} -gt 0 ]]; then
  # Service-account ID tokens must carry the Cloud Run URL as audience.
  audience="${url%/mcp}"
  token="$(gcloud auth print-identity-token "${impersonate[@]}" --include-email --audiences="$audience" 2>/dev/null)"
  printf '{"Authorization": "Bearer %s"}\n' "$token"
else
  token="$(gcloud auth print-identity-token 2>/dev/null)"
  printf '{"Authorization": "Bearer %s"}\n' "$token"
fi
