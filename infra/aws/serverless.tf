# ── SNS Topic ──────────────────────────────────────────────────────────────────
resource "aws_sns_topic" "user_verification" {
  name = "${var.environment}-user-verification"

  tags = {
    Name = "${var.environment}-user-verification"
  }
}

# ── DynamoDB Table (email token tracking) ─────────────────────────────────────
resource "aws_dynamodb_table" "email_tokens" {
  name         = "${var.environment}-email-tokens"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email"

  attribute {
    name = "email"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name = "${var.environment}-email-tokens"
  }
}

# ── Lambda IAM Role ────────────────────────────────────────────────────────────
resource "aws_iam_role" "lambda_role" {
  name = "${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "${var.environment}-lambda-role"
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.environment}-lambda-policy"
  description = "Allow Lambda to write logs and access DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.email_tokens.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# ── Lambda Function ────────────────────────────────────────────────────────────
resource "aws_lambda_function" "email_verification" {
  function_name    = "${var.environment}-email-verification"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  timeout          = 30

  environment {
    variables = {
      SENDGRID_API_KEY = var.sendgrid_api_key
      FROM_EMAIL       = var.from_email
      DYNAMODB_TABLE   = aws_dynamodb_table.email_tokens.name
      BASE_URL         = "https://${var.domain_name}"
    }
  }

  tags = {
    Name = "${var.environment}-email-verification"
  }
}

# ── SNS → Lambda Subscription ──────────────────────────────────────────────────
resource "aws_sns_topic_subscription" "lambda" {
  topic_arn = aws_sns_topic.user_verification.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.email_verification.arn
}

resource "aws_lambda_permission" "sns_invoke" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.email_verification.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.user_verification.arn
}

# ── EC2 SNS Publish Policy ─────────────────────────────────────────────────────
resource "aws_iam_policy" "sns_publish" {
  name        = "${var.environment}-ec2-sns-publish"
  description = "Allow EC2 instances to publish to the user verification SNS topic"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sns:Publish"
      Resource = aws_sns_topic.user_verification.arn
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sns_publish" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.sns_publish.arn
}
