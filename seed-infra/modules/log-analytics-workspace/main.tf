resource "azurerm_log_analytics_workspace" "this" {
  name                       = var.name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  sku                        = "PerGB2018"
  retention_in_days          = 30
  internet_ingestion_enabled = var.internet_ingestion_enabled
  internet_query_enabled     = var.internet_query_enabled
  tags                       = var.tags
}
