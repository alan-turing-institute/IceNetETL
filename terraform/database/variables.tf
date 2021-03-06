variable "allowed_cidrs" {
  type        = map(string)
  description = "List of CIDRs that users can connect from"
}
variable "database_names" {
  description = "List of database names"
  type        = list(string)
}
variable "key_vault_id" {
  description = "ID of the KeyVault where secrets are stored"
  type        = string
}
variable "logging_workspace_id" {
  description = "ID of the Azure log analytics workspace"
  type        = string
}
variable "postgres_cores" {
  description = "Number of cores for the PostgreSQL server."
  type        = number
  default     = 2
}
variable "postgresql_configurations" {
  description = "PostgreSQL configurations to apply to the server."
  type        = map(string)
  default = {
    "idle_in_transaction_session_timeout" : "18000000"
  }
}
variable "postgresql_version" {
  description = "PostgreSQL version used by the server."
  type        = number
  default     = 11
}
variable "storage_mb" {
  description = "Max storage allowed for the PostgreSQL server in MB."
  type        = number
}
variable "resource_group_name" {
  type        = string
  description = "Resource group of the storage account"
}

# Load common module
module "common" {
  source = "../common"
}

# Local variables
locals {
  tags = merge(
    {
      "module" = "database"
    },
    module.common.tags,
  )
  db_name = "psql-${module.common.project_name}-database"
}
