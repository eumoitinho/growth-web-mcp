terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 7.0, < 9.0"
    }
  }
  # Recommended: keep state in GCS.
  # backend "gcs" { bucket = "<project>-tfstate" prefix = "growth-web-mcp" }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  registry = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.mcp.repository_id}"

  apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "analyticsadmin.googleapis.com",
    "analyticsdata.googleapis.com",
    "googleads.googleapis.com",
    "tagmanager.googleapis.com",
    "bigquery.googleapis.com",
  ]

  # Every MCP server is its own Cloud Run service. Read services are always
  # deployed; write services only with var.enable_write, filtered by var.write_servers.
  read_services = {
    ga4 = {
      image    = "ga4"
      sa       = google_service_account.google_reader.email
      env      = {}
      secrets  = {}
      cpu      = "1"
      memory   = "1Gi"
      max      = 3
      affinity = false
    }
    google-ads = {
      image = "google-ads"
      sa    = google_service_account.google_reader.email
      env = merge(
        { GOOGLE_PROJECT_ID = var.project_id },
        var.google_ads_login_customer_id == "" ? {} : { GOOGLE_ADS_LOGIN_CUSTOMER_ID = var.google_ads_login_customer_id },
      )
      secrets  = { GOOGLE_ADS_DEVELOPER_TOKEN = google_secret_manager_secret.ads_developer_token.secret_id }
      cpu      = "1"
      memory   = "1Gi"
      max      = 3
      affinity = false
    }
    gtm = {
      image    = "gtm"
      sa       = google_service_account.google_reader.email
      env      = { GTM_ACCESS_MODE = "read" }
      secrets  = {}
      cpu      = "1"
      memory   = "512Mi"
      max      = 3
      affinity = false
    }
    hubspot = {
      image    = "hubspot"
      sa       = google_service_account.hubspot_reader.email
      env      = { HUBSPOT_ACCESS_MODE = "read" }
      secrets  = { PRIVATE_APP_ACCESS_TOKEN = google_secret_manager_secret.hubspot_read_token.secret_id }
      cpu      = "1"
      memory   = "512Mi"
      max      = 3
      affinity = false
    }
    site-browser = {
      image   = "site-browser"
      sa      = google_service_account.site_browser.email
      env     = {}
      secrets = {}
      cpu     = "2"
      memory  = "4Gi"
      # Stateful MCP sessions (one headless Chrome each) live in one instance's
      # memory; the MCP clients do not keep Cloud Run's affinity cookie, so a
      # second instance answers "Session not found".
      max      = 1
      affinity = true
    }
    meta = {
      image    = "meta"
      sa       = google_service_account.meta_reader.email
      env      = {}
      secrets  = { META_ACCESS_TOKEN = google_secret_manager_secret.meta_read_token.secret_id }
      cpu      = "1"
      memory   = "512Mi"
      max      = 3
      affinity = false
    }
  }

  gtm_write     = var.enable_write && contains(var.write_servers, "gtm-write")
  hubspot_write = var.enable_write && contains(var.write_servers, "hubspot-write")

  write_services = var.enable_write ? { for k, v in {
    gtm-write = {
      image = "gtm"
      sa    = one(google_service_account.gtm_writer[*].email)
      env = {
        GTM_ACCESS_MODE   = "write"
        GTM_ALLOW_DELETE  = tostring(var.gtm_write_allow_delete)
        GTM_ALLOW_PUBLISH = tostring(var.gtm_write_allow_publish)
      }
      secrets  = {}
      cpu      = "1"
      memory   = "512Mi"
      max      = 1
      affinity = false
    }
    hubspot-write = {
      image = "hubspot"
      sa    = one(google_service_account.hubspot_writer[*].email)
      env = {
        HUBSPOT_ACCESS_MODE = "write"
        HUBSPOT_WRITE_TOOLS = join(",", var.hubspot_write_tools)
      }
      secrets  = { PRIVATE_APP_ACCESS_TOKEN = one(google_secret_manager_secret.hubspot_write_token[*].secret_id) }
      cpu      = "1"
      memory   = "512Mi"
      max      = 1
      affinity = false
    }
  } : k => v if contains(var.write_servers, k) } : {}

  services = merge(local.read_services, local.write_services)
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "mcp" {
  repository_id = "growth-mcp"
  location      = var.region
  format        = "DOCKER"
  description   = "Images of the growth-web-mcp servers"
  depends_on    = [google_project_service.apis]
}

# ---- Cloud Run -----------------------------------------------------------------

resource "google_cloud_run_v2_service" "mcp" {
  for_each            = local.services
  name                = "growth-mcp-${each.key}"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = { app = "growth-web-mcp", access = contains(keys(local.write_services), each.key) ? "write" : "read" }

  template {
    service_account                  = each.value.sa
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "3600s"
    session_affinity                 = each.value.affinity
    max_instance_request_concurrency = each.value.affinity ? 4 : 40

    scaling {
      min_instance_count = 0
      max_instance_count = each.value.max
    }

    containers {
      image = "${local.registry}/${each.value.image}:${var.image_tag}"
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = each.value.cpu
          memory = each.value.memory
        }
        cpu_idle = true
      }
      dynamic "env" {
        for_each = each.value.env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = each.value.secrets
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
    google_project_service.apis,
    google_secret_manager_secret_iam_member.accessors,
  ]
}

# Only IAM principals with roles/run.invoker can reach the servers.
resource "google_cloud_run_v2_service_iam_member" "read_invokers" {
  for_each = {
    for pair in setproduct(keys(local.read_services), concat(var.invokers, ["serviceAccount:${google_service_account.agent.email}"])) :
    "${pair[0]}|${pair[1]}" => { service = pair[0], member = pair[1] }
  }
  name     = google_cloud_run_v2_service.mcp[each.value.service].name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value.member
}

resource "google_cloud_run_v2_service_iam_member" "write_invokers" {
  for_each = {
    for pair in setproduct(keys(local.write_services), var.write_invokers) :
    "${pair[0]}|${pair[1]}" => { service = pair[0], member = pair[1] }
  }
  name     = google_cloud_run_v2_service.mcp[each.value.service].name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value.member
}
