variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "internet_ingestion_enabled" {
  description = "Whether ingestion may use the public Azure Monitor endpoint. Set false only with private-link ingestion connectivity."
  type        = bool
}

variable "internet_query_enabled" {
  description = "Whether queries may use the public Azure Monitor endpoint. Set false only with private-link query connectivity."
  type        = bool
}
