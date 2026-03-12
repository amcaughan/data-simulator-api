# data-simulator-api

Synthetic event simulation API infrastructure and application code.

This repository contains:
- API application code for the simulator
- Terragrunt/Terraform infrastructure for deploying it
- local development tooling
- CI for static analysis and security scanning

`aws_infra` manages the AWS account baseline.
This repository manages only the simulator application's code and infrastructure.

Repository structure

- `app/` for application code
- `infra/terragrunt/modules/` for Terraform modules local to this repo
- `infra/terragrunt/live/` for deployable stacks
- `local/` for local development tooling

Current MVP

- Lambda deployed as a zip package
- private REST API Gateway enabled for `dev` and scoped to the shared dev VPC from `aws_infra`
- private API invoke URL published to SSM for easy cross-repo lookup
- direct dependencies declared in `app/requirements.in`
- deployable dependency lockfile compiled to `app/requirements.txt`
- package build performed by Terraform during apply

Usage

Infrastructure is applied manually via Terragrunt.
CI should remain limited to static analysis and security scanning unless there is a deliberate reason to automate deploys.

License

MIT
