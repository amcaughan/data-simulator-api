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
  value = var.private_api_enabled ? aws_api_gateway_rest_api.private[0].id : null
}

output "private_api_stage_name" {
  value = var.private_api_enabled ? aws_api_gateway_stage.private[0].stage_name : null
}

output "private_api_invoke_url" {
  value = var.private_api_enabled ? "https://${aws_api_gateway_rest_api.private[0].id}.execute-api.${data.aws_region.current.region}.amazonaws.com/${aws_api_gateway_stage.private[0].stage_name}" : null
}

output "private_api_dns_name" {
  value = var.private_api_enabled && var.private_api_dns_name != null ? aws_route53_record.private_api_cname[0].fqdn : null
}

output "private_api_dns_invoke_url" {
  value = var.private_api_enabled && var.private_api_dns_name != null ? "https://${aws_route53_record.private_api_cname[0].fqdn}/${aws_api_gateway_stage.private[0].stage_name}" : null
}
