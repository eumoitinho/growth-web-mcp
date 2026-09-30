variable "project_id" {
  description = "Google Cloud project that hosts the MCP servers and the clean BigQuery dataset."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run and Artifact Registry."
  type        = string
  default     = "southamerica-east1"
}

variable "image_tag" {
  description = "Tag of the images built by cloudbuild.yaml (e.g. a commit SHA). 'latest' is fine to start."
  type        = string
  default     = "latest"
}

variable "invokers" {
  description = "Members allowed to call the READ servers, e.g. [\"group:growth@example.com\"]. The agent service account is always added."
  type        = list(string)
  default     = []
}

# ---- Write access (opt-in) ---------------------------------------------------

variable "enable_write" {
  description = "Deploy the separate WRITE services (gtm-write, hubspot-write) with their own service accounts."
  type        = bool
  default     = false
}

variable "write_servers" {
  description = "Which WRITE services to deploy when enable_write = true: gtm-write, hubspot-write."
  type        = list(string)
  default     = ["gtm-write", "hubspot-write"]
}

variable "write_invokers" {
  description = "Members allowed to call the WRITE servers. Keep this list short; the read agent SA is NOT included automatically."
  type        = list(string)
  default     = []
}

variable "gtm_write_allow_delete" {
  description = "Allow the GTM write server to remove tags/triggers/variables."
  type        = bool
  default     = false
}

variable "gtm_write_allow_publish" {
  description = "Allow the GTM write server to publish versions (changes go live). Strongly recommended: false."
  type        = bool
  default     = false
}

variable "hubspot_write_tools" {
  description = "Subset of upstream HubSpot write tools to enable on hubspot-write. Empty = all of them."
  type        = list(string)
  default     = ["hubspot-batch-update-objects", "hubspot-create-property", "hubspot-update-property"]
}

# ---- Data ----------------------------------------------------------------------

variable "ga4_export_project" {
  description = "Project holding the GA4 BigQuery export. Empty = project_id. Applying the grant needs BigQuery admin on that dataset."
  type        = string
  default     = ""
}

variable "ga4_export_dataset" {
  description = "BigQuery dataset of the GA4 export (analytics_<property_id>), in ga4_export_project. Empty to skip grants."
  type        = string
  default     = ""
}

variable "clean_dataset" {
  description = "BigQuery dataset holding the curated views (the agent's clean surface)."
  type        = string
  default     = "growth_clean"
}

variable "bigquery_location" {
  description = "Location of the clean dataset. Must match the GA4 export dataset location."
  type        = string
  default     = "US"
}

variable "google_ads_login_customer_id" {
  description = "Manager (MCC) account ID used as login-customer-id, digits only. Empty if not using an MCC."
  type        = string
  default     = ""
}

# ---- claude.ai connector (servers/gateway, infra/terraform/gateway.tf) -----------

variable "enable_gateway" {
  description = "Deploy the public OAuth gateway that exposes the READ servers to claude.ai custom connectors."
  type        = bool
  default     = false
}

variable "gateway_oauth_client_id" {
  description = "Google OAuth client ID (Web application, Internal consent screen) used by the gateway's sign-in."
  type        = string
  default     = ""
}

variable "gateway_allowed_domains" {
  description = "Google Workspace domains whose verified accounts may use the connector."
  type        = list(string)
  default     = []
}

variable "wordpress_mcp_url" {
  description = "WordPress MCP Adapter endpoint proxied by the gateway (credential in secret wordpress-mcp-basic-auth)."
  type        = string
  default     = ""
}
