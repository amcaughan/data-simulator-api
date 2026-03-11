variable "app_dir" {
  type = string
}

variable "description" {
  type    = string
  default = "Data simulator API Lambda"
}

variable "environment" {
  type = string
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "function_name" {
  type = string
}

variable "handler" {
  type    = string
  default = "handler.handler"
}

variable "log_retention_in_days" {
  type    = number
  default = 14
}

variable "memory_size_mb" {
  type    = number
  default = 256
}

variable "reserved_concurrent_executions" {
  type    = number
  default = 1
}

variable "runtime" {
  type    = string
  default = "python3.12"
}

variable "timeout_seconds" {
  type    = number
  default = 5
}
