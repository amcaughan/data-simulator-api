data "aws_region" "current" {}

data "aws_ssm_parameter" "private_api_allowed_vpc" {
  name = var.private_api_allowed_vpc_ssm_param_name
}

locals {
  private_api_stage_name = coalesce(var.private_api_stage_name, var.environment)
}

data "aws_iam_policy_document" "private_api_policy" {
  statement {
    sid    = "AllowPrivateInvokeFromSharedVpc"
    effect = "Allow"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["execute-api:Invoke"]
    resources = ["execute-api:/*"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceVpc"
      values   = [data.aws_ssm_parameter.private_api_allowed_vpc.value]
    }
  }
}

resource "aws_cloudwatch_log_group" "private_api_access" {
  name              = "/aws/apigateway/${var.function_name}-private"
  retention_in_days = var.private_api_log_retention_in_days
}

resource "aws_api_gateway_rest_api" "private" {
  name        = "${var.function_name}-private"
  description = "Private REST API for ${var.function_name}"
  policy      = data.aws_iam_policy_document.private_api_policy.json

  endpoint_configuration {
    types = ["PRIVATE"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_rest_api.private.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_resource" "v1" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_rest_api.private.root_resource_id
  path_part   = "v1"
}

resource "aws_api_gateway_resource" "distributions" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "distributions"
}

resource "aws_api_gateway_resource" "distribution_sample" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.distributions.id
  path_part   = "sample"
}

resource "aws_api_gateway_resource" "distribution_generate" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.distributions.id
  path_part   = "generate"
}

resource "aws_api_gateway_resource" "scenarios" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "scenarios"
}

resource "aws_api_gateway_resource" "scenario_sample" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.scenarios.id
  path_part   = "sample"
}

resource "aws_api_gateway_resource" "scenario_generate" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.scenarios.id
  path_part   = "generate"
}

resource "aws_api_gateway_resource" "presets" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "presets"
}

resource "aws_api_gateway_resource" "preset_id" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.presets.id
  path_part   = "{preset_id}"
}

resource "aws_api_gateway_resource" "preset_generate" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.preset_id.id
  path_part   = "generate"
}

resource "aws_api_gateway_resource" "preset_sample" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_resource.preset_id.id
  path_part   = "sample"
}

locals {
  private_api_routes = {
    health_get = {
      resource_id        = aws_api_gateway_resource.health.id
      http_method        = "GET"
      request_parameters = {}
    }
    distributions_sample_post = {
      resource_id        = aws_api_gateway_resource.distribution_sample.id
      http_method        = "POST"
      request_parameters = {}
    }
    distributions_generate_post = {
      resource_id        = aws_api_gateway_resource.distribution_generate.id
      http_method        = "POST"
      request_parameters = {}
    }
    scenarios_sample_post = {
      resource_id        = aws_api_gateway_resource.scenario_sample.id
      http_method        = "POST"
      request_parameters = {}
    }
    scenarios_generate_post = {
      resource_id        = aws_api_gateway_resource.scenario_generate.id
      http_method        = "POST"
      request_parameters = {}
    }
    presets_get = {
      resource_id        = aws_api_gateway_resource.presets.id
      http_method        = "GET"
      request_parameters = {}
    }
    preset_generate_post = {
      resource_id = aws_api_gateway_resource.preset_generate.id
      http_method = "POST"
      request_parameters = {
        "method.request.path.preset_id" = true
      }
    }
    preset_sample_post = {
      resource_id = aws_api_gateway_resource.preset_sample.id
      http_method = "POST"
      request_parameters = {
        "method.request.path.preset_id" = true
      }
    }
  }
}

resource "aws_api_gateway_method" "route" {
  for_each = local.private_api_routes

  rest_api_id        = aws_api_gateway_rest_api.private.id
  resource_id        = each.value.resource_id
  http_method        = each.value.http_method
  authorization      = "AWS_IAM"
  request_parameters = each.value.request_parameters
}

resource "aws_api_gateway_integration" "route" {
  for_each = local.private_api_routes

  rest_api_id             = aws_api_gateway_rest_api.private.id
  resource_id             = each.value.resource_id
  http_method             = aws_api_gateway_method.route[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.this.invoke_arn
}

resource "aws_api_gateway_deployment" "private" {
  rest_api_id = aws_api_gateway_rest_api.private.id

  triggers = {
    redeployment = sha1(jsonencode({
      resource_ids = {
        distribution_generate = aws_api_gateway_resource.distribution_generate.id
        distribution_sample   = aws_api_gateway_resource.distribution_sample.id
        distributions         = aws_api_gateway_resource.distributions.id
        health                = aws_api_gateway_resource.health.id
        preset_generate       = aws_api_gateway_resource.preset_generate.id
        preset_id             = aws_api_gateway_resource.preset_id.id
        preset_sample         = aws_api_gateway_resource.preset_sample.id
        presets               = aws_api_gateway_resource.presets.id
        scenario_generate     = aws_api_gateway_resource.scenario_generate.id
        scenario_sample       = aws_api_gateway_resource.scenario_sample.id
        scenarios             = aws_api_gateway_resource.scenarios.id
        v1                    = aws_api_gateway_resource.v1.id
      }
      method_ids      = { for route_name, route in aws_api_gateway_method.route : route_name => route.id }
      integration_ids = { for route_name, route in aws_api_gateway_integration.route : route_name => route.id }
    }))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "private" {
  rest_api_id   = aws_api_gateway_rest_api.private.id
  deployment_id = aws_api_gateway_deployment.private.id
  stage_name    = local.private_api_stage_name

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.private_api_access.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      sourceIp         = "$context.identity.sourceIp"
      requestTime      = "$context.requestTime"
      httpMethod       = "$context.httpMethod"
      path             = "$context.path"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      integrationError = "$context.integrationErrorMessage"
      apiId            = "$context.apiId"
      stage            = "$context.stage"
    })
  }

  depends_on = [
    aws_api_gateway_account.this,
  ]
}

resource "aws_api_gateway_method_settings" "private" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  stage_name  = aws_api_gateway_stage.private.stage_name
  method_path = "*/*"

  settings {
    logging_level      = "ERROR"
    metrics_enabled    = true
    data_trace_enabled = false
  }
}

resource "aws_ssm_parameter" "private_api_invoke_url" {
  count = var.private_api_url_ssm_param_name != null ? 1 : 0

  name  = var.private_api_url_ssm_param_name
  type  = "String"
  value = "https://${aws_api_gateway_rest_api.private.id}.execute-api.${data.aws_region.current.region}.amazonaws.com/${aws_api_gateway_stage.private.stage_name}"
}

resource "aws_lambda_permission" "private_api_gateway" {
  statement_id  = "AllowPrivateApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.private.execution_arn}/*/*"
}
