terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 5.0, < 7.0" }
  }
}
resource "aws_secretsmanager_secret" "runtime" {
  name_prefix             = "labshop-runtime-"
  description             = "Dedicated PostgreSQL labshop_app credentials, provisioned by SSM"
  recovery_window_in_days = 7
}
resource "aws_iam_role_policy" "bootstrap" {
  name_prefix = "labshop-bootstrap-"
  role        = var.application_role_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = var.master_secret_arn },
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"], Resource = aws_secretsmanager_secret.runtime.arn }
    ]
  })
}
resource "aws_ssm_association" "application" {
  for_each                         = var.application_instances
  name                             = "AWS-RunShellScript"
  association_name                 = "labshop-app-${each.key}"
  wait_for_success_timeout_seconds = 1800
  targets {
    key    = "InstanceIds"
    values = [each.value.id]
  }
  parameters = {
    executionTimeout = "1500"
    commands = templatefile("${path.module}/bootstrap.sh.tftpl", {
      repository_url = var.repository_url
      commit         = var.commit
      role           = "app"
      config_b64 = base64encode(jsonencode({
        region             = var.region
        db_host            = var.db_host
        db_name            = var.db_name
        master_secret_arn  = var.master_secret_arn
        runtime_secret_arn = aws_secretsmanager_secret.runtime.arn
        mode               = var.mode
        cookie_secure      = var.cookie_secure
        redeploy_token     = var.redeploy_token
      }))
    })
  }
  depends_on = [aws_iam_role_policy.bootstrap]
}
resource "aws_ssm_association" "web" {
  for_each                         = var.web_instance_ids
  name                             = "AWS-RunShellScript"
  association_name                 = "labshop-web-${each.key}"
  wait_for_success_timeout_seconds = 1800
  targets {
    key    = "InstanceIds"
    values = [each.value]
  }
  parameters = {
    executionTimeout = "1500"
    commands = templatefile("${path.module}/bootstrap.sh.tftpl", {
      repository_url = var.repository_url
      commit         = var.commit
      role           = "web"
      config_b64 = base64encode(jsonencode({
        upstreams      = [for node in var.application_instances : node.private_ip]
        mode           = var.mode
        redeploy_token = var.redeploy_token
      }))
    })
  }
  depends_on = [aws_ssm_association.application]
}
output "runtime_secret_arn" { value = aws_secretsmanager_secret.runtime.arn }
output "application_associations" { value = { for k, a in aws_ssm_association.application : k => a.association_id } }
output "web_associations" { value = { for k, a in aws_ssm_association.web : k => a.association_id } }
