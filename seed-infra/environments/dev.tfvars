# Development sandbox only. Values here are examples, not credentials.
environment                 = "dev"
sandbox_resource_group_name = "rg-platt-sandbox"
location                    = "westeurope"

# Replace before first real apply if this name is already taken globally.
storage_account_name = "plattdev001sa"

tags = {
  Application = "platt"
  Environment = "dev"
  ManagedBy   = "terraform"
  Owner       = "platform-team@example.invalid"
  CostCenter  = "sandbox"
}

additional_tags = {
  DataClassification = "internal"
}
