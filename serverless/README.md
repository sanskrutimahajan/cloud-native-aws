# Serverless — Email Verification Lambda

AWS Lambda function triggered by an SNS notification to send account verification emails to newly registered users. Duplicate emails are prevented by tracking sent emails in DynamoDB.

```
EC2 Web App ──publishes──► SNS Topic ──triggers──► Lambda ──sends email──► SendGrid
                                                       │
                                                       └──records──► DynamoDB
```

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| Python 3.12+ | Matching the Lambda runtime |
| pip | Installing dependencies |
| AWS CLI | Deploying the Lambda function |
| SendGrid account | Sending transactional email (free tier sufficient) |

---

## Repository Structure

```
.
├── lambda_function.py    # Lambda handler (entry point: lambda_function.lambda_handler)
├── requirements.txt      # Runtime dependencies
├── .gitignore
└── README.md
```

---

## Build & Deploy Instructions

### 1. Install dependencies into the package directory

```bash
pip install -r requirements.txt -t package/
cp lambda_function.py package/
```

### 2. Create the deployment zip

```bash
cd package && zip -r ../lambda_package.zip . && cd ..
```

### 3. Deploy to AWS Lambda

```bash
aws lambda update-function-code \
  --function-name email-verification \
  --zip-file fileb://lambda_package.zip
```

Or on first deploy, create the function via the AWS Console or Terraform in the [`infra/`](../infra/) folder of this repo (`infra/aws/serverless.tf`).

### 4. Set environment variables on the Lambda function

```bash
aws lambda update-function-configuration \
  --function-name email-verification \
  --environment "Variables={
    DYNAMODB_TABLE=email-tracking,
    BASE_URL=http://your-ec2-url,
    SENDGRID_API_KEY=your-sendgrid-api-key,
    FROM_EMAIL=noreply@yourdomain.com
  }"
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DYNAMODB_TABLE` | Yes | DynamoDB table name for tracking sent emails |
| `BASE_URL` | Yes | Web app base URL used to build the verification link |
| `SENDGRID_API_KEY` | Yes | SendGrid API key |
| `FROM_EMAIL` | Yes | Sender email address (must be verified in SendGrid) |

---

## SNS Message Format

The web application publishes a JSON message to the SNS topic when a new user registers:

```json
{
  "email": "user@example.com",
  "first_name": "Jane",
  "token": "550e8400-e29b-41d4-a716-446655440000"
}
```

The verification link sent to the user:

```
http://<BASE_URL>/validateEmail?email=user%40example.com&token=<UUID>
```

---

## Duplicate Prevention

1. On each invocation the Lambda queries DynamoDB for the user's email.
2. If a record exists, the email was already sent — the function skips without sending.
3. DynamoDB is written **only after** a successful SendGrid API call, so SNS retries on failure are safe.
