output "mcp_urls" {
  description = "Streamable HTTP endpoints (append nothing: they already end in /mcp)."
  value       = { for k, s in google_cloud_run_v2_service.mcp : k => "${s.uri}/mcp" }
}

output "service_accounts" {
  description = "Emails to grant in each product UI (docs/access-setup.md)."
  value = merge(
    {
      google_reader  = google_service_account.google_reader.email
      hubspot_reader = google_service_account.hubspot_reader.email
      site_browser   = google_service_account.site_browser.email
      meta_reader    = google_service_account.meta_reader.email
      agent          = google_service_account.agent.email
    },
    local.gtm_write ? { gtm_writer = google_service_account.gtm_writer[0].email } : {},
    local.hubspot_write ? { hubspot_writer = google_service_account.hubspot_writer[0].email } : {},
  )
}

output "artifact_registry" {
  value = local.registry
}

output "gateway" {
  description = "claude.ai connector URL and the redirect URI to register in the Google OAuth client."
  value = var.enable_gateway ? {
    connector_url      = "${local.gateway_url}/mcp"
    oauth_redirect_uri = "${local.gateway_url}/auth/callback"
  } : null
}
