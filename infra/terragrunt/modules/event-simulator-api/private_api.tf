data "aws_region" "current" {}

data "aws_ssm_parameter" "private_api_allowed_vpc" {
  count = var.private_api_enabled ? 1 : 0

  name = var.private_api_allowed_vpc_ssm_param_name
}

locals {
  private_api_stage_name = coalesce(var.private_api_stage_name, var.environment)
}

data "aws_iam_policy_document" "private_api_policy" {
  count = var.private_api_enabled ? 1 : 0

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
      values   = [data.aws_ssm_parameter.private_api_allowed_vpc[0].value]
    }
  }
}

resource "aws_cloudwatch_log_group" "private_api_access" {
  count = var.private_api_enabled ? 1 : 0

  name              = "/aws/apigateway/${var.function_name}-private"
  retention_in_days = var.private_api_log_retention_in_days
}

resource "aws_api_gateway_rest_api" "private" {
  count = var.private_api_enabled ? 1 : 0

  name        = "${var.function_name}-private"
  description = "Private REST API for ${var.function_name}"
  policy      = data.aws_iam_policy_document.private_api_policy[0].json

  endpoint_configuration {
    types = ["PRIVATE"]
  }
}

resource "aws_api_gateway_resource" "proxy" {
  count = var.private_api_enabled ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.private[0].id
  parent_id   = aws_api_gateway_rest_api.private[0].root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy_any" {
  count = var.private_api_enabled ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.private[0].id
  resource_id   = aws_api_gateway_resource.proxy[0].id
  http_method   = "ANY"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "proxy_any" {
  count = var.private_api_enabled ? 1 : 0

  rest_api_id             = aws_api_gateway_rest_api.private[0].id
  resource_id             = aws_api_gateway_resource.proxy[0].id
  http_method             = aws_api_gateway_method.proxy_any[0].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.this.invoke_arn
}

resource "aws_api_gateway_deployment" "private" {
  count = var.private_api_enabled ? 1 : 0

  rest_api_id = aws_api_gateway_rest_api.private[0].id

  triggers = {
    redeployment = sha1(jsonencode({
      proxy_integration = aws_api_gateway_integration.proxy_any[0].id
      proxy_method      = aws_api_gateway_method.proxy_any[0].id
      proxy_resource    = aws_api_gateway_resource.proxy[0].id
    }))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "private" {
  count = var.private_api_enabled ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.private[0].id
  deployment_id = aws_api_gateway_deployment.private[0].id
  stage_name    = local.private_api_stage_name

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.private_api_access[0].arn
    format = jsonencode({
      requestId              = "$context.requestId"
      sourceIp               = "$context.identity.sourceIp"
      requestTime            = "$context.requestTime"
      httpMethod             = "$context.httpMethod"
      path                   = "$context.path"
      status                 = "$context.status"
      responseLength         = "$context.responseLength"
      integrationError       = "$context.integrationErrorMessage"
      apiId                  = "$context.apiId"
      stage                  = "$context.stage"
    })
  }
}

resource "aws_lambda_permission" "private_api_gateway" {
  count = var.private_api_enabled ? 1 : 0

  statement_id  = "AllowPrivateApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.private[0].execution_arn}/*/*"
}
