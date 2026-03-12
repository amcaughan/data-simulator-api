output "function_arn" {
  value = aws_lambda_function.this.arn
}

output "function_name" {
  value = aws_lambda_function.this.function_name
}

output "invoke_arn" {
  value = aws_lambda_function.this.invoke_arn
}

output "dlq_arn" {
  value = aws_sqs_queue.dlq.arn
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.url
}

output "private_api_id" {
  value = aws_api_gateway_rest_api.private.id
}

output "private_api_stage_name" {
  value = aws_api_gateway_stage.private.stage_name
}

output "private_api_invoke_url" {
  value = "https://${aws_api_gateway_rest_api.private.id}.execute-api.${data.aws_region.current.region}.amazonaws.com/${aws_api_gateway_stage.private.stage_name}"
}
