include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/infra/terragrunt/modules/event-simulator-api"
}

inputs = {
  app_dir                          = "${get_repo_root()}/app"
  description                      = "Development Lambda for the data simulator API"
  environment                      = "dev"
  function_name                    = "data-simulator-api-dev"
  log_retention_in_days            = 14
  memory_size_mb                   = 256
  private_api_allowed_vpc_ssm_param_name = "/network/dev/vpc/vpc_id"
  private_api_enabled                    = true
  private_api_stage_name                 = "dev"
  reserved_concurrent_executions   = 1
  timeout_seconds                  = 5
  environment_variables = {
    LOG_LEVEL = "INFO"
  }
}
