# Serverless — Email Verification Lambda

AWS Lambda function that listens on an SNS topic and sends account verification emails to newly registered users. Duplicate sends are prevented by tracking sent emails in DynamoDB.

```
EC2 Web App ──publishes──► SNS Topic ──triggers──► Lambda ──sends email──► Mailgun
                                                       │
                                                       └──records──► DynamoDB
```

---

## Prerequisites

To build and deploy this project locally you need:

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Local development and matching the Lambda runtime |
| pip | latest | Installing Python dependencies |
| Terraform | ≥ 1.5 | Provisioning AWS infrastructure |
| AWS CLI | ≥ 2.x | Authenticating with AWS |
| zip | any | Creating the Lambda deployment package |
| Mailgun account | — | Sending transactional email (free tier sufficient) |

**AWS credentials** must be configured before running Terraform:

```bash
aws configure
# or export AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
```

**Mailgun** — create an account at https://app.mailgun.com, add a sending domain, and obtain your API key from the dashboard.

---

## Repository Structure

```
.
├── lambda/
│   └── index.py              # Lambda handler (entry point: index.handler)
├── terraform/
│   ├── providers.tf          # Terraform and provider version constraints
│   ├── variables.tf          # All input variable declarations
│   ├── iam.tf                # IAM roles and policies (Lambda + EC2)
│   ├── dynamodb.tf           # DynamoDB table for email deduplication
│   ├── sns.tf                # SNS topic, subscription, and Lambda permission
│   ├── lambda.tf             # Lambda function resource
│   ├── outputs.tf            # Output values (SNS ARN, instance profile, etc.)
│   └── terraform.tfvars.example  # Template for required variable values
├── requirements.txt          # Python dependencies for local development
└── README.md
```

---

## Build Instructions

The Lambda function uses only the Python standard library and `boto3`, which is pre-installed in the AWS Lambda runtime. No dependency packaging step is required.

If you add new third-party packages in the future, install them into the `lambda/` directory before running `terraform apply`:

```bash
pip install <package> -t lambda/
```

Terraform automatically creates `lambda_package.zip` from the `lambda/` directory when you run `terraform apply`. You do not need to zip anything manually.

---

## Deploy Instructions

### 1. Configure variables

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars` and fill in all placeholder values:

| Variable | Description |
|----------|-------------|
| `aws_region` | AWS region to deploy into (e.g. `us-east-1`) |
| `base_url` | Base URL of your web application (e.g. `http://your-ec2-ip`) |
| `mailgun_api_key` | Your Mailgun private API key |
| `mailgun_domain` | Your Mailgun sending domain (e.g. `mg.yourdomain.com`) |
| `email_sender` | From address for verification emails |

> **Never commit `terraform.tfvars`** — it contains secrets and is excluded by `.gitignore`.

### 2. Initialize Terraform

```bash
cd terraform
terraform init
```

### 3. Review the plan

```bash
terraform plan
```

### 4. Apply

```bash
terraform apply
```

Type `yes` when prompted. After a successful apply, Terraform prints key output values:

```
sns_topic_arn              = "arn:aws:sns:us-east-1:123456789:user-registration"
ec2_instance_profile_name  = "ec2-webapp-instance-profile"
dynamodb_table_name        = "email-tracking"
lambda_function_name       = "email-verification"
```

### 5. Wire up the web application

Set the following environment variable in your web application so it can publish to SNS:

```
SNS_TOPIC_ARN=<value of sns_topic_arn output>
```

Attach the EC2 instance profile printed in `ec2_instance_profile_name` to your EC2 instance so the web app has permission to publish to SNS without hardcoded credentials.

---

## Teardown

```bash
cd terraform
terraform destroy
```

---

## Environment Variables Reference (Lambda)

| Variable | Required | Description |
|----------|----------|-------------|
| `DYNAMODB_TABLE` | Yes | DynamoDB table name for tracking sent emails |
| `BASE_URL` | Yes | Web app base URL used to build the verification link |
| `MAILGUN_API_KEY` | Yes | Mailgun private API key |
| `MAILGUN_DOMAIN` | Yes | Mailgun sending domain |
| `EMAIL_SENDER` | No | From address (defaults to `noreply@<MAILGUN_DOMAIN>`) |
| `LOG_LEVEL` | No | Logging verbosity — `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |

---

## SNS Message Format

The web application must publish a JSON message to the SNS topic in this format:

```json
{
  "email": "user@example.com",
  "first_name": "Jane",
  "token": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `email` | Yes | User's email address — also the DynamoDB partition key |
| `first_name` | No | Used to personalise the greeting |
| `token` | Yes | UUID generated by the web app and stored in its database |

The verification link sent to the user will be:

```
<BASE_URL>/validateEmail?email=<email>&token=<token>
```

---

## How Duplicate Prevention Works

1. On every invocation, the Lambda checks DynamoDB for an existing item with `email` as the key.
2. If an item is found, the email has already been sent — the function logs the skip and exits cleanly.
3. Only after a successful Mailgun API call does the function write the item to DynamoDB.
4. Because the check happens before the send, SNS retries on transient failures are safe.
