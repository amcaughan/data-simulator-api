include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_repo_root()}/infra/terragrunt/modules/event-simulator-api"
}

inputs = {
  environment = "dev"
}
