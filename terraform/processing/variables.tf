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
  # Basic      B1    1 core  1.75 GB RAM  £ 51.24 / month
  # Standard   S1    1 core  1.75 GB RAM  £ 68.14 / month
  # PremiumV2  P1v2  1 core  3.5  GB RAM  £136.28 / month
  # PremiumV2  P2v2  2 core  7    GB RAM  £272.55 / month
  # PremiumV3  P1v3  2 core  8    GB RAM  £181.52 / month
  app_sku_category = "PremiumV3"
  app_sku          = "P1v3"
}
