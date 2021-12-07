# Create the resource group
resource "azurerm_resource_group" "this" {
  name     = "rg-${module.common.project_name}-processing"
  location = module.common.location
  tags     = local.tags
}

# For storing logs
resource "azurerm_application_insights" "this" {
  name                = "insights-${module.common.project_name}-processing"
  location            = module.common.location
  resource_group_name = azurerm_resource_group.this.name
  application_type    = "web"
  tags                = local.tags
}

# Create the storage account
resource "azurerm_storage_account" "this" {
  name                     = "st${module.common.project_name}processing"
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  account_tier             = "Standard"
  account_kind             = "StorageV2"
  account_replication_type = "LRS"
  tags                     = local.tags
}

# Storage container for deploying functions
resource "azurerm_storage_container" "this" {
  name                  = "deployments"
  storage_account_name  = azurerm_storage_account.this.name
  container_access_type = "private"
}

# Service plan that functions belong to
resource "azurerm_app_service_plan" "this" {
  name                = "plan-${module.common.project_name}-processing"
  resource_group_name = azurerm_resource_group.this.name
  location            = module.common.location
  kind                = "Linux"
  reserved            = true
  sku {
    tier = local.app_sku_category
    size = local.app_sku
  }
  lifecycle {
    ignore_changes = [kind]
  }
  tags = local.tags
}

# Functions to be deployed
resource "azurerm_function_app" "this" {
  name                       = local.app_name
  location                   = module.common.location
  resource_group_name        = azurerm_resource_group.this.name
  app_service_plan_id        = azurerm_app_service_plan.this.id
  storage_account_name       = var.data_storage_account.name
  storage_account_access_key = var.data_storage_account.primary_access_key
  os_type                    = "linux"
  version                    = "~3"
  site_config {
    always_on                 = true
    linux_fx_version          = "Python|3.9"
    use_32_bit_worker_process = false
  }
  app_settings = {
    "APPINSIGHTS_INSTRUMENTATIONKEY"        = "${azurerm_application_insights.this.instrumentation_key}"
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = "InstrumentationKey=${azurerm_application_insights.this.instrumentation_key}"
    "ENABLE_ORYX_BUILD"                     = "true"
    "FUNCTIONS_WORKER_RUNTIME"              = "python"
    "PSQL_DB"                               = var.database_name
    "PSQL_HOST"                             = var.database_fqdn
    "PSQL_PWD"                              = var.database_password
    "PSQL_USER"                             = var.database_user
    "SCM_DO_BUILD_DURING_DEPLOYMENT"        = "1"
  }
  tags = local.tags
}

# Actual function deployment
resource "null_resource" "functions" {
  # These define build order
  depends_on = [azurerm_app_service_plan.this, azurerm_function_app.this]

  # These will trigger a redeploy
  triggers = {
    functions    = "${local.version}_${join("+", [for value in local.functions : value["name"]])}"
    service_plan = "${azurerm_app_service_plan.this.id}_${azurerm_app_service_plan.this.sku[0].tier}_${azurerm_app_service_plan.this.sku[0].size}"
    function_app = "${azurerm_function_app.this.id}_${azurerm_function_app.this.site_config[0].linux_fx_version}"
  }

  provisioner "local-exec" {
    command = <<EOF
    echo "Waiting for other deployments to finish..."
    sleep 150
    cd ../azfunctions
    echo "Deploying functions from $(pwd)"
    func azure functionapp publish ${local.app_name} --python
    cd -
    EOF
  }
}
