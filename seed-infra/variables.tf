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

variable "location" {
  description = "Azure region for sandbox resources."
  type        = string
}

variable "tags" {
  description = "Mandatory governance tags; all listed keys are required."
  type        = map(string)

  validation {
    condition = alltrue([
      for key in ["Application", "Environment", "ManagedBy", "Owner", "CostCenter"] :
      contains(keys(var.tags), key) && try(trimspace(var.tags[key]), "") != ""
    ])
    error_message = "tags must include non-empty Application, Environment, ManagedBy, Owner, and CostCenter values."
  }
}

variable "additional_tags" {
  description = "Optional tags merged with mandatory tags. Mandatory tag keys cannot be overridden."
  type        = map(string)
  default     = {}

  validation {
    condition = length(setintersection(
      toset(keys(var.additional_tags)),
      toset(["Application", "Environment", "ManagedBy", "Owner", "CostCenter"])
    )) == 0
    error_message = "additional_tags cannot override mandatory governance tags."
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
