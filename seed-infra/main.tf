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
  mandatory_tag_keys = {
    Application = "application"
    Environment = "environment"
    ManagedBy   = "managedby"
    Owner       = "owner"
    CostCenter  = "costcenter"
  }
  mandatory_tags = merge({
    for canonical_key, normalized_key in local.mandatory_tag_keys :
    canonical_key => one([for key, value in var.tags : value if lower(key) == normalized_key])
    }, {
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
