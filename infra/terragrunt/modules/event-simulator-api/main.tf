terraform {
  required_version = ">= 1.5.0"
}

variable "environment" {
  type = string
}

output "environment" {
  value = var.environment
}
