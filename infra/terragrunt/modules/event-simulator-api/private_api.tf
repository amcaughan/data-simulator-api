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

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.private.id
  parent_id   = aws_api_gateway_rest_api.private.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy_any" {
  rest_api_id   = aws_api_gateway_rest_api.private.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "proxy_any" {
  rest_api_id             = aws_api_gateway_rest_api.private.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy_any.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.this.invoke_arn
}

resource "aws_api_gateway_deployment" "private" {
  rest_api_id = aws_api_gateway_rest_api.private.id

  triggers = {
    redeployment = sha1(jsonencode({
      proxy_integration = aws_api_gateway_integration.proxy_any.id
      proxy_method      = aws_api_gateway_method.proxy_any.id
      proxy_resource    = aws_api_gateway_resource.proxy.id
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
