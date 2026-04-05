output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway"
  value       = aws_internet_gateway.main.id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "public_route_table_id" {
  description = "ID of public route table"
  value       = aws_route_table.public.id
}

output "private_route_table_id" {
  description = "ID of private route table"
  value       = aws_route_table.private.id
}

output "application_security_group_id" {
  description = "ID of the application security group"
  value       = aws_security_group.application.id
}

output "database_security_group_id" {
  description = "ID of the database security group"
  value       = aws_security_group.database.id
}

output "load_balancer_security_group_id" {
  description = "ID of the load balancer security group"
  value       = aws_security_group.load_balancer.id
}

output "alb_dns_name" {
  description = "DNS name of the application load balancer"
  value       = aws_lb.app.dns_name
}

output "s3_bucket_name" {
  description = "Name of the S3 syllabus bucket"
  value       = aws_s3_bucket.syllabus.bucket
}

output "rds_endpoint" {
  description = "RDS instance hostname"
  value       = aws_db_instance.main.address
}

output "rds_port" {
  description = "RDS instance port"
  value       = aws_db_instance.main.port
}

output "iam_role_arn" {
  description = "ARN of the EC2 IAM role"
  value       = aws_iam_role.ec2_role.arn
}

output "iam_instance_profile_name" {
  description = "Name of the EC2 instance profile"
  value       = aws_iam_instance_profile.ec2_profile.name
}

output "application_url" {
  description = "Application URL via load balancer and domain name"
  value       = "http://${var.domain_name}/"
}

output "sns_topic_arn" {
  description = "ARN of the user verification SNS topic"
  value       = aws_sns_topic.user_verification.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB email tokens table"
  value       = aws_dynamodb_table.email_tokens.name
}

output "lambda_function_name" {
  description = "Name of the email verification Lambda function"
  value       = aws_lambda_function.email_verification.function_name
}

output "kms_key_ec2_arn" {
  description = "ARN of the EC2 KMS key"
  value       = aws_kms_key.ec2.arn
}

output "kms_key_rds_arn" {
  description = "ARN of the RDS KMS key"
  value       = aws_kms_key.rds.arn
}

output "kms_key_s3_arn" {
  description = "ARN of the S3 KMS key"
  value       = aws_kms_key.s3.arn
}

output "kms_key_secrets_arn" {
  description = "ARN of the Secrets Manager KMS key"
  value       = aws_kms_key.secrets.arn
}

output "secret_arn_db_password" {
  description = "ARN of the DB password secret in Secrets Manager"
  value       = aws_secretsmanager_secret.db_password.arn
}

output "secret_arn_sendgrid_api_key" {
  description = "ARN of the SendGrid API key secret in Secrets Manager"
  value       = aws_secretsmanager_secret.sendgrid_api_key.arn
}
