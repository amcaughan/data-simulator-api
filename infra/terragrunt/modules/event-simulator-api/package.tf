terraform {
  required_version = ">= 1.5.0"

  required_providers {
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.5"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

locals {
  app_files   = fileset(var.app_dir, "**")
  build_root  = "${path.module}/.lambda-build"
  build_dir   = "${local.build_root}/${var.function_name}"
  package_zip = "${local.build_root}/${var.function_name}.zip"
}

resource "null_resource" "package" {
  triggers = {
    app_hash = sha256(join("", [
      for file_name in local.app_files : filesha256("${var.app_dir}/${file_name}")
    ]))
    architecture     = var.architecture
    package_script   = filesha256("${path.module}/package_lambda.sh")
    runtime          = var.runtime
    requirements_txt = fileexists("${var.app_dir}/requirements.txt") ? file("${var.app_dir}/requirements.txt") : ""
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = "\"${path.module}/package_lambda.sh\" \"${var.app_dir}\" \"${local.build_dir}\" \"${var.runtime}\" \"${var.architecture}\""
  }
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = local.build_dir
  output_path = local.package_zip

  depends_on = [null_resource.package]
}
