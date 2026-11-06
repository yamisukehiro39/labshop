variable "repository_url" {
  type        = string
  description = "Public GitHub repository without credentials"
  validation {
    condition     = can(regex("^https://github[.]com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+[.]git$", var.repository_url))
    error_message = "Use https://github.com/OWNER/REPO.git without a token."
  }
}
variable "commit" {
  type        = string
  description = "Immutable full Git SHA; change it to deploy a new release"
  validation {
    condition     = can(regex("^[a-f0-9]{40}$", var.commit))
    error_message = "Provide a full 40-character lowercase Git commit SHA."
  }
}
variable "application_instances" {
  type = map(object({ id = string, private_ip = string }))
  validation {
    condition     = length(var.application_instances) > 0
    error_message = "At least one application instance is required."
  }
}
variable "web_instance_ids" {
  type = map(string)
  validation {
    condition     = length(var.web_instance_ids) > 0
    error_message = "At least one web instance is required."
  }
}
variable "application_role_name" { type = string }
variable "db_host" { type = string }
variable "db_name" { type = string }
variable "master_secret_arn" { type = string }
variable "region" {
  type    = string
  default = "eu-west-3"
}
variable "mode" {
  type    = string
  default = "secure"
  validation {
    condition     = contains(["secure", "vulnerable"], var.mode)
    error_message = "Mode must be secure or vulnerable."
  }
}
variable "cookie_secure" {
  type        = bool
  default     = true
  description = "Set false only for existing HTTP-only lab ALB"
}
variable "redeploy_token" {
  type        = string
  default     = "1"
  description = "Increment to rerun same commit (e.g. secret refresh); never place secrets here"
}
