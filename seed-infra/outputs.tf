output "resource_group_name" {
  description = "Existing sandbox resource group targeted by this configuration."
  value       = data.azurerm_resource_group.sandbox.name
}

output "storage_account_id" {
  description = "ID of the managed sandbox storage account."
  value       = module.storage_account.id
}

output "log_analytics_workspace_id" {
  description = "ID of the managed sandbox Log Analytics workspace."
  value       = module.log_analytics_workspace.id
}
