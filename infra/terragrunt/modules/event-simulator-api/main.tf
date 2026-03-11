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
    runtime          = var.runtime
    requirements_txt = fileexists("${var.app_dir}/requirements.txt") ? file("${var.app_dir}/requirements.txt") : ""
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = "\"${path.module}/package_lambda.sh\" \"${var.app_dir}\" \"${local.build_dir}\""
  }
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = local.build_dir
  output_path = local.package_zip

  depends_on = [null_resource.package]
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_in_days
}

resource "aws_lambda_function" "this" {
  function_name = var.function_name
  description   = var.description
  role          = aws_iam_role.lambda.arn
  runtime       = var.runtime
  handler       = var.handler
  timeout       = var.timeout_seconds
  memory_size   = var.memory_size_mb

  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  reserved_concurrent_executions = var.reserved_concurrent_executions

  environment {
    variables = merge(
      {
        ENVIRONMENT = var.environment
      },
      var.environment_variables
    )
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.basic_execution,
  ]
}
