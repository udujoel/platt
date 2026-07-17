data "azurerm_resource_group" "sandbox" {
  name = var.sandbox_resource_group_name
}

module "naming" {
  source = "./modules/naming"

  project     = var.project
  environment = var.environment
  instance    = var.instance
}

locals {
  mandatory_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
  })
  common_tags          = merge(local.mandatory_tags, var.additional_tags)
  storage_account_name = coalesce(var.storage_account_name, module.naming.storage_account_name)
}

module "storage_account" {
  source = "./modules/storage-account"

  name                = local.storage_account_name
  resource_group_name = data.azurerm_resource_group.sandbox.name
  location            = data.azurerm_resource_group.sandbox.location
  tags                = local.common_tags
}
module "log_analytics_workspace" {
  source = "./modules/log-analytics-workspace"

  name                = module.naming.log_analytics_workspace_name
  resource_group_name = data.azurerm_resource_group.sandbox.name
  location            = data.azurerm_resource_group.sandbox.location
  tags                = local.common_tags
}
