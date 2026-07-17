output "storage_account_name" {
  description = "Storage account name that follows Azure lowercase-alphanumeric requirements."
  value       = "${local.compact_prefix}sa"
}

output "log_analytics_workspace_name" {
  description = "Log Analytics workspace name following the repository convention."
  value       = "law-${local.dashed_prefix}"
}
