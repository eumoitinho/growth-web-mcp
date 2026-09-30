# Public MCP gateway for claude.ai connectors (servers/gateway).
#
# The read servers stay private (IAM). This one service is reachable without a
# Google ID token because claude.ai speaks MCP OAuth instead: the gateway runs
# Google Sign-In itself, accepts only verified accounts in var.gateway_allowed_domains,
# and calls the read servers with its own service account.
#
# Enable in two steps (docs/claude-web-connector.md):
#   1. enable_gateway = true with -target on the secrets, add their versions;
#   2. full apply.

data "google_project" "this" {}

locals {
  gateway_url = "https://growth-mcp-gateway-${data.google_project.this.number}.${var.region}.run.app"

  gateway_secrets = var.enable_gateway ? {
    GOOGLE_OAUTH_CLIENT_SECRET = "gateway-google-oauth-client-secret"
    GATEWAY_JWT_KEY            = "gateway-jwt-signing-key"
    GATEWAY_STORAGE_KEY        = "gateway-storage-key"
    WP_MCP_BASIC_AUTH          = "wordpress-mcp-basic-auth"
  } : {}

  gateway_upstreams = {
    GROWTH_MCP_GA4_URL          = "ga4"
    GROWTH_MCP_GOOGLE_ADS_URL   = "google-ads"
    GROWTH_MCP_GTM_URL          = "gtm"
    GROWTH_MCP_HUBSPOT_URL      = "hubspot"
    GROWTH_MCP_META_URL         = "meta"
    GROWTH_MCP_SITE_BROWSER_URL = "site-browser"
  }
}

resource "google_project_service" "firestore" {
  count              = var.enable_gateway ? 1 : 0
  service            = "firestore.googleapis.com"
  disable_on_destroy = false
}

# OAuth client registrations and tokens (encrypted by the gateway), so a
# redeploy does not log everybody out.
resource "google_firestore_database" "gateway" {
  count       = var.enable_gateway ? 1 : 0
  name        = "mcp-gateway"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.firestore]
}

resource "google_service_account" "gateway" {
  count        = var.enable_gateway ? 1 : 0
  account_id   = "mcp-gateway"
  display_name = "growth-web-mcp: public gateway for claude.ai (invokes the read servers)"
}

resource "google_secret_manager_secret" "gateway" {
  for_each  = toset(values(local.gateway_secrets))
  secret_id = each.value
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "gateway" {
  for_each  = google_secret_manager_secret.gateway
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.gateway[0].member
}

resource "google_project_iam_member" "gateway_firestore" {
  count   = var.enable_gateway ? 1 : 0
  project = var.project_id
  role    = "roles/datastore.user"
  member  = google_service_account.gateway[0].member
  condition {
    title      = "mcp-gateway database only"
    expression = "resource.name.startsWith(\"projects/${var.project_id}/databases/mcp-gateway\")"
  }
}

# The gateway reaches every READ server; never the write ones.
resource "google_cloud_run_v2_service_iam_member" "gateway_invoker" {
  for_each = var.enable_gateway ? local.read_services : {}
  name     = google_cloud_run_v2_service.mcp[each.key].name
  location = var.region
  role     = "roles/run.invoker"
  member   = google_service_account.gateway[0].member
}

resource "google_cloud_run_v2_service" "gateway" {
  count               = var.enable_gateway ? 1 : 0
  name                = "growth-mcp-gateway"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  # Public on purpose: authentication happens in the app (MCP OAuth + Google).
  invoker_iam_disabled = true
  labels               = { app = "growth-web-mcp", access = "read" }

  template {
    service_account                  = google_service_account.gateway[0].email
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "3600s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      # One instance: each person's site-browser session lives in its memory.
      max_instance_count = 1
    }

    containers {
      image = "${local.registry}/gateway:${var.image_tag}"
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle = true
      }
      env {
        name  = "GATEWAY_BASE_URL"
        value = local.gateway_url
      }
      env {
        name  = "GATEWAY_ALLOWED_DOMAINS"
        value = join(",", var.gateway_allowed_domains)
      }
      env {
        name  = "GOOGLE_OAUTH_CLIENT_ID"
        value = var.gateway_oauth_client_id
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GATEWAY_FIRESTORE_DATABASE"
        value = google_firestore_database.gateway[0].name
      }
      env {
        name  = "WP_MCP_URL"
        value = var.wordpress_mcp_url
      }
      dynamic "env" {
        for_each = local.gateway_upstreams
        content {
          name  = env.key
          value = "${google_cloud_run_v2_service.mcp[env.value].uri}/mcp"
        }
      }
      dynamic "env" {
        for_each = local.gateway_secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.gateway,
    google_project_iam_member.gateway_firestore,
  ]
}
