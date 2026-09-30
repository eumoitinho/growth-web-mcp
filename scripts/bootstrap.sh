#!/usr/bin/env bash
# First deploy, end to end. Re-runnable.
#   PROJECT_ID=your-gcp-project REGION=southamerica-east1 scripts/bootstrap.sh
# Requires: gcloud (authenticated as a project owner), terraform >= 1.6,
# and infra/terraform/terraform.tfvars (copy terraform.tfvars.example).
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-southamerica-east1}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/infra/terraform"

echo "==> 1/5 APIs, Artifact Registry, service accounts, secrets"
terraform -chdir="$TF_DIR" init -input=false
terraform -chdir="$TF_DIR" apply -input=false -auto-approve \
  -target=google_project_service.apis \
  -target=google_artifact_registry_repository.mcp \
  -target=google_secret_manager_secret.hubspot_read_token \
  -target=google_secret_manager_secret.ads_developer_token \
  -target=google_secret_manager_secret.meta_read_token \
  -target=google_secret_manager_secret.hubspot_write_token

echo "==> 2/5 Secret values (skipped when a version already exists)"
add_secret() {
  local secret="$1" prompt="$2"
  if gcloud secrets versions list "$secret" --project "$PROJECT_ID" --limit 1 --format='value(name)' | grep -q .; then
    echo "    $secret: already has a version"
  else
    read -r -s -p "    $prompt: " value; echo
    printf '%s' "$value" | gcloud secrets versions add "$secret" --project "$PROJECT_ID" --data-file=-
  fi
}
add_secret hubspot-private-app-token-read "HubSpot private app token (READ-ONLY scopes)"
add_secret google-ads-developer-token "Google Ads developer token"
add_secret meta-system-user-token-read "Meta system user token (ads_read, read_insights, ...)"
if terraform -chdir="$TF_DIR" state list | grep -q hubspot_write_token; then
  add_secret hubspot-private-app-token-write "HubSpot private app token (WRITE scopes)"
fi

echo "==> 3/5 Build images (tag $TAG)"
gcloud builds submit "$ROOT" --project "$PROJECT_ID" --config "$ROOT/cloudbuild.yaml" \
  --substitutions="_REGION=$REGION,_TAG=$TAG"

echo "==> 4/5 Cloud Run services and IAM"
terraform -chdir="$TF_DIR" apply -input=false -auto-approve -var "image_tag=$TAG"

echo "==> 5/5 Google-managed BigQuery MCP server"
echo "    nothing to enable: it only needs bigquery.googleapis.com (step 1) and roles/mcp.toolUser (Terraform)"

echo
terraform -chdir="$TF_DIR" output mcp_urls
terraform -chdir="$TF_DIR" output service_accounts
echo "Next: grant the service accounts in GA4 / Google Ads / GTM and the Meta system user (docs/access-setup.md),"
echo "      then scripts/write-env.sh > .env and run scripts/bq-apply.sh."
