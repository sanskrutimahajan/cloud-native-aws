# ── DB Password (auto-generated) ──────────────────────────────────────────────
resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.environment}-db-password"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 0

  tags = {
    Name = "${var.environment}-db-password"
  }
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}

# ── SendGrid API Key ───────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "sendgrid_api_key" {
  name                    = "${var.environment}-sendgrid-api-key"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 0

  tags = {
    Name = "${var.environment}-sendgrid-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "sendgrid_api_key" {
  secret_id     = aws_secretsmanager_secret.sendgrid_api_key.id
  secret_string = var.sendgrid_api_key
}
