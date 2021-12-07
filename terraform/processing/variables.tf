# Load common module
module "common" {
  source = "../common"
}
variable "data_storage_account" {
  description = "Storage account containing input data"
}
variable "database_fqdn" {
  description = "Database server FQDN"
  type        = string
}
variable "database_host" {
  description = "Database server hostname"
  type        = string
}
variable "database_name" {
  description = "Database name"
  type        = string
}
variable "database_user" {
  description = "Database username"
  type        = string
}
variable "database_password" {
  description = "Database username"
  type        = string
}
variable "database_resource_group_name" {
  type        = string
  description = "Resource group of the storage account"
}
# Local variables
locals {
  tags = merge(
    {
      "module" = "processing"
    },
    module.common.tags,
  )
  version   = yamldecode(file("../azfunctions/config.yaml"))["version"]
  functions = yamldecode(file("../azfunctions/config.yaml"))["functions"]
  app_name  = "app-${module.common.project_name}-processing"
  # https://azure.microsoft.com/en-us/pricing/details/app-service/windows/
  # Basic B1: 1 core, 1.75 GB memory £51.48/month
  # Standard S1: 1 core, 1.75 GB memory £68.46/month
  # Premium P1V2: 1 core, 3.5 GB memory £136.91/month
  # Premium P1V3: 1 core, 8 GB memory £182.36/month
  app_sku_category = "PremiumV2"
  app_sku          = "P1v2"
}
