#!/usr/bin/env bash
# Renders and applies the clean surface (dim table + views) in order.
#   PROJECT_ID=your-gcp-project scripts/bq-apply.sh [--dry-run]
# Optional: GA4_PROJECT / GA4_DATASET (default: config/site-scope.yaml),
# CLEAN_DATASET (growth_clean), LOOKBACK_DAYS (180).
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY=()
[[ "${1:-}" == "--dry-run" ]] && DRY=(--dry_run)

python3 "$ROOT/scripts/render_bq.py" --project "$PROJECT_ID" \
  --clean "${CLEAN_DATASET:-growth_clean}" --lookback-days "${LOOKBACK_DAYS:-180}" \
  ${GA4_PROJECT:+--ga4-project "$GA4_PROJECT"} \
  ${GA4_DATASET:+--ga4-dataset "$GA4_DATASET"} >/dev/null

for f in "$ROOT"/bigquery/build/*.sql; do
  echo "==> $(basename "$f")"
  bq query --project_id="$PROJECT_ID" --use_legacy_sql=false --quiet "${DRY[@]}" < "$f"
done
