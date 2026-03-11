resource "aws_sqs_queue" "dlq" {
  name              = "${var.function_name}-dlq"
  kms_master_key_id = "alias/aws/sqs"
}
