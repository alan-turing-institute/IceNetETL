# Secrets module
module "secrets" {
  source              = "./secrets"
  developers_group_id = var.developers_group_id
  tenant_id           = var.tenant_id
}

# Data storage
module "data" {
  source = "./data"
}

# Logging module
module "logging" {
  source = "./logging"
}

# Database module
module "database" {
  source               = "./database"
  resource_group_name  = module.data.rg_name
  storage_mb           = 5120
  allowed_cidrs        = var.users_ip_addresses
  key_vault_id         = module.secrets.key_vault_id
  logging_workspace_id = module.logging.logging_workspace_id
  database_names       = local.database_names
}

# NetCDF processing
module "processing" {
  source                       = "./processing"
  data_storage_account         = module.data.storage_account
  database_resource_group_name = module.data.rg_name
  database_fqdn                = module.database.server_fqdn
  database_host                = module.database.server_name
  database_name                = local.database_names[0]
  database_user                = module.database.admin_username
  database_password            = module.database.admin_password
}
