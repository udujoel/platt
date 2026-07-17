variable "project" {
  description = "Short lowercase project identifier used in Azure resource names."
  type        = string
  default     = "platt"

  validation {
    condition     = can(regex("^[a-z0-9]{2,10}$", var.project))
    error_message = "project must contain 2-10 lowercase letters or numbers."
  }
}

variable "environment" {
  description = "Deployment environment name. This reference project supports the sandbox dev environment."
  type        = string

  validation {
    condition     = contains(["dev"], var.environment)
    error_message = "Only the dev sandbox environment is permitted by this reference configuration."
  }
}

variable "instance" {
  description = "Two or three digit instance suffix used by the naming module."
  type        = string
  default     = "001"

  validation {
    condition     = can(regex("^[0-9]{2,3}$", var.instance))
    error_message = "instance must be a two or three digit number."
  }
}

variable "sandbox_resource_group_name" {
  description = "Existing sandbox resource group. Terraform must not create or manage this resource group."
  type        = string
}

variable "tags" {
  description = "Mandatory governance tags; all listed keys are required."
  type        = map(string)

  validation {
    condition = length(distinct([for key in keys(var.tags) : lower(key)])) == length(keys(var.tags)) && alltrue([
      for required_key in ["application", "environment", "managedby", "owner", "costcenter"] :
      length([for key, value in var.tags : key if lower(key) == required_key && trimspace(value) != ""]) == 1
    ])
    error_message = "tags must include exactly one non-empty Application, Environment, ManagedBy, Owner, and CostCenter value (case-insensitive)."
  }
}

variable "additional_tags" {
  description = "Optional tags merged with mandatory tags. Mandatory tag keys cannot be overridden."
  type        = map(string)
  default     = {}

  validation {
    condition = length(distinct([for key in keys(var.additional_tags) : lower(key)])) == length(keys(var.additional_tags)) && length(setintersection(
      toset([for key in keys(var.additional_tags) : lower(key)]),
      toset(["application", "environment", "managedby", "owner", "costcenter"])
    )) == 0
    error_message = "additional_tags cannot override mandatory governance tags, including by a casing variant."
  }
}

variable "storage_account_name" {
  description = "Optional globally unique storage-account override. Leave null to use the repository naming convention."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.storage_account_name == null || can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "storage_account_name must be null or contain 3-24 lowercase alphanumeric characters."
  }
}
