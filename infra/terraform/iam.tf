# Service accounts. None of them gets GA4 / Ads / GTM access from Terraform:
# those grants are made in each product's UI (see docs/access-setup.md),
# which is exactly what keeps read and write identities separate.

resource "google_service_account" "google_reader" {
  account_id   = "mcp-google-reader"
  display_name = "growth-web-mcp: GA4 / Google Ads / GTM read-only"
  description  = "Add as Viewer in GA4, Read-only in Google Ads, Read in GTM."
}

resource "google_service_account" "hubspot_reader" {
  account_id   = "mcp-hubspot-reader"
  display_name = "growth-web-mcp: HubSpot read (secret access only)"
}

resource "google_service_account" "meta_reader" {
  account_id   = "mcp-meta-reader"
  display_name = "growth-web-mcp: Meta Ads read (secret access only)"
}

resource "google_service_account" "site_browser" {
  account_id   = "mcp-site-browser"
  display_name = "growth-web-mcp: headless Chrome (no roles on purpose)"
}

resource "google_service_account" "agent" {
  account_id   = "growth-agent"
  display_name = "growth-web-mcp: server-side agent identity"
  description  = "Invokes the read MCP servers and queries the clean BigQuery surface."
}

resource "google_service_account" "gtm_writer" {
  count        = local.gtm_write ? 1 : 0
  account_id   = "mcp-gtm-writer"
  display_name = "growth-web-mcp: GTM write (Edit, no Publish)"
  description  = "Add in GTM with container permission Edit (or Approve). Publish only if gtm_write_allow_publish."
}

resource "google_service_account" "hubspot_writer" {
  count        = local.hubspot_write ? 1 : 0
  account_id   = "mcp-hubspot-writer"
  display_name = "growth-web-mcp: HubSpot write (secret access only)"
}

# ---- Secrets (values are added out of band, never in Terraform state) -------------

resource "google_secret_manager_secret" "hubspot_read_token" {
  secret_id = "hubspot-private-app-token-read"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "hubspot_write_token" {
  count     = local.hubspot_write ? 1 : 0
  secret_id = "hubspot-private-app-token-write"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "meta_read_token" {
  secret_id = "meta-system-user-token-read"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "ads_developer_token" {
  secret_id = "google-ads-developer-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

locals {
  secret_accessors = merge(
    {
      hubspot_read = { secret = google_secret_manager_secret.hubspot_read_token.id, member = google_service_account.hubspot_reader.member }
      ads_token    = { secret = google_secret_manager_secret.ads_developer_token.id, member = google_service_account.google_reader.member }
      meta_read    = { secret = google_secret_manager_secret.meta_read_token.id, member = google_service_account.meta_reader.member }
    },
    local.hubspot_write ? {
      hubspot_write = { secret = google_secret_manager_secret.hubspot_write_token[0].id, member = google_service_account.hubspot_writer[0].member }
    } : {},
  )
}

resource "google_secret_manager_secret_iam_member" "accessors" {
  for_each  = local.secret_accessors
  secret_id = each.value.secret
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value.member
}

# ---- BigQuery: the clean surface -----------------------------------------------

resource "google_bigquery_dataset" "clean" {
  dataset_id  = var.clean_dataset
  location    = var.bigquery_location
  description = "Curated views over the GA4 export (see bigquery/). The agent's single source of truth for inbound analysis."
  depends_on  = [google_project_service.apis]
}

locals {
  # Everyone who uses the read servers (humans in var.invokers + the agent SA)
  # also gets the BigQuery MCP and the clean dataset.
  analysts = concat(var.invokers, [google_service_account.agent.member])
}

resource "google_project_iam_member" "analyst_project_roles" {
  for_each = {
    for pair in setproduct(["roles/bigquery.jobUser", "roles/mcp.toolUser"], local.analysts) :
    "${pair[0]}|${pair[1]}" => { role = pair[0], member = pair[1] }
  }
  project = var.project_id
  role    = each.value.role # mcp.toolUser: Google-managed remote MCP servers (BigQuery MCP)
  member  = each.value.member
}

resource "google_bigquery_dataset_iam_member" "analyst_clean_viewer" {
  for_each   = toset(local.analysts)
  dataset_id = google_bigquery_dataset.clean.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = each.value
}

# The clean views are plain (not authorized) views, so querying them needs read
# access to the raw GA4 export too.
resource "google_bigquery_dataset_iam_member" "analyst_export_viewer" {
  for_each   = var.ga4_export_dataset == "" ? toset([]) : toset(local.analysts)
  project    = var.ga4_export_project == "" ? var.project_id : var.ga4_export_project
  dataset_id = var.ga4_export_dataset
  role       = "roles/bigquery.dataViewer"
  member     = each.value
}
