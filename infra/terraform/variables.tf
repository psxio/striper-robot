variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "strype"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "image_url" {
  type = string
}

variable "certificate_arn" {
  type    = string
  default = ""
}

variable "database_name" {
  type    = string
  default = "strype"
}

variable "database_username" {
  type = string
}

variable "database_password" {
  type      = string
  sensitive = true
}

variable "database_url_secret_arn" {
  type = string
}

variable "secret_key_secret_arn" {
  type = string
}

variable "stripe_secret_key_secret_arn" {
  type    = string
  default = ""
}

variable "stripe_webhook_secret_arn" {
  type    = string
  default = ""
}

variable "sendgrid_api_key_secret_arn" {
  type    = string
  default = ""
}

variable "sentry_dsn_secret_arn" {
  type    = string
  default = ""
}

variable "frontend_url" {
  type = string
}

variable "cors_origins" {
  type = string
}
