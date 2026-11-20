# tf-infra

Infrastructure as Code — Terraform configurations for AWS networking, compute, database, storage, IAM, KMS, Secrets Manager, serverless, CloudWatch observability, DNS, and SSL.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.0
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with `dev` and `demo` profiles
- A custom AMI built via Packer with the CloudWatch Unified Agent and application pre-installed

## Repository Structure

```
tf-infra/
├── .github/workflows/
│   └── terraform-ci.yml        # CI: fmt, init, validate on every PR
├── aws/
│   ├── providers.tf            # AWS + random provider configuration
│   ├── main.tf                 # VPC, subnets, security groups, S3, RDS, IAM, launch template, ALB, ASG, Route 53
│   ├── serverless.tf           # SNS, DynamoDB, Lambda (email verification), EC2 SNS publish policy
│   ├── kms.tf                  # 4 customer-managed KMS keys with 90-day rotation
│   ├── secrets.tf              # Secrets Manager secrets for DB password and SendGrid API key
│   ├── ssl.tf                  # ACM certificate with Route 53 DNS validation
│   ├── variables.tf            # Input variable declarations
│   ├── outputs.tf              # Output value declarations
│   ├── dev.tfvars              # Dev environment values (gitignored)
│   └── demo.tfvars             # Demo environment values (gitignored)
```

## What Gets Created

### Networking
- VPC with DNS support and hostnames enabled
- 3 public subnets + 3 private subnets across 3 availability zones
- Internet Gateway, public route table, private route table
- **Load balancer security group** — HTTPS (443) inbound from internet only
- **Application security group** — app port (8080) inbound from LB SG only; no SSH
- **Database security group** — DB port (5432) inbound from application SG only

### SSL / HTTPS
- ACM certificate issued via DNS validation (works for both dev and demo — both use Route 53)
- Route 53 CNAME record created automatically for DNS validation
- ALB HTTPS listener on port 443 using `ELBSecurityPolicy-TLS13-1-2-2021-06`
- Traffic from ALB → EC2 uses plain HTTP (internal only, not exposed)

### Storage
- S3 bucket (UUID-named) encrypted with **SSE-KMS** using the S3 KMS key
- Bucket key enabled to reduce KMS API calls
- Public access fully blocked
- 30-day lifecycle transition to STANDARD_IA

### Database
- RDS PostgreSQL in private subnets with dedicated subnet group and parameter group
- **Storage encrypted** with the RDS KMS key
- Password **auto-generated** by Terraform (`random_password`) and stored in Secrets Manager

### KMS Keys (90-day rotation, customer-managed)
| Key | Purpose |
|-----|---------|
| `<env>-ec2` | EBS volume encryption for ASG instances |
| `<env>-rds` | RDS storage encryption |
| `<env>-s3` | S3 bucket SSE-KMS encryption |
| `<env>-secrets` | Secrets Manager secret encryption |

### Secrets Manager
| Secret | Contents |
|--------|---------|
| `<env>-db-password` | Auto-generated RDS password (16 chars, special chars) |
| `<env>-sendgrid-api-key` | SendGrid API key for email verification Lambda |

Both secrets encrypted with the `<env>-secrets` KMS key.

### IAM
- **EC2 role** with:
  - S3 access (PutObject, GetObject, DeleteObject) + KMS Decrypt/GenerateDataKey for S3 key
  - CloudWatch Agent (PutMetricData, logs, ec2:Describe*, ssm:GetParameter)
  - Secrets Manager GetSecretValue scoped to the DB password secret
  - KMS Decrypt scoped to the Secrets Manager key
  - SNS Publish scoped to the user verification topic
- **Lambda role** with:
  - CloudWatch Logs
  - DynamoDB (PutItem, GetItem, UpdateItem) on the email tokens table
  - Secrets Manager GetSecretValue scoped to the SendGrid API key secret
  - KMS Decrypt scoped to the Secrets Manager key
- EC2 instance profile wrapping the EC2 role — no credentials stored on instances

### Compute (Auto Scaling)
- Launch Template (`csye6225_asg`):
  - Custom AMI, t2.micro
  - EBS root volume (25GB gp2) **encrypted** with EC2 KMS key
  - No SSH key pair — instances are not directly accessible
  - User data fetches DB password from Secrets Manager at launch and writes `/opt/csye6225/.env`
- Auto Scaling Group: min 3, max 5, desired 3 across public subnets
- Scale-up policy: CPU > 5% for 2 periods → add 1 instance
- Scale-down policy: CPU < 3% for 2 periods → remove 1 instance

### Load Balancer
- Application Load Balancer (internet-facing) across 3 public subnets
- Target group on port 8080 (HTTP), health check on `/healthz`
- HTTPS listener on port 443 with ACM certificate

### Serverless (Email Verification)
- SNS topic `<env>-user-verification` — EC2 publishes user registration events
- DynamoDB table `<env>-email-tokens` — tracks verification tokens with TTL
- Lambda function `<env>-email-verification` (Python 3.12):
  - Triggered by SNS
  - Reads SendGrid API key from Secrets Manager secret version (passed as env var)
  - Sends verification email with a link containing the token
  - Writes token to DynamoDB with expiry

### DNS
- Route 53 A record (alias) pointing `<env>.sansmah.me` to the ALB

### Observability
- CloudWatch Unified Agent started via user data on instance launch
- Application logs shipped to CloudWatch Log Groups
- Custom StatsD metrics on `:8125`

---

## tfvars Setup

`*.tfvars` files are gitignored (they contain secrets). Create them locally before deploying.

### dev.tfvars

```hcl
aws_region       = "us-east-1"
aws_profile      = "dev"
environment      = "dev"
vpc_name         = "csye6225-vpc"
vpc_cidr         = "10.0.0.0/16"
application_port = 8080
database_port    = 5432

public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
availability_zones   = ["us-east-1a", "us-east-1b", "us-east-1c"]

ami_id        = "<AMI_ID_FROM_PACKER>"
instance_type = "t2.micro"

db_identifier             = "csye6225"
db_name                   = "csye6225"
db_username               = "csye6225"
db_engine                 = "postgres"
db_engine_version         = "16.3"
db_parameter_group_family = "postgres16"
db_instance_class         = "db.t3.micro"

route53_zone_id = "<DEV_HOSTED_ZONE_ID>"
domain_name     = "dev.sansmah.me"

lambda_zip_path  = "../serverless/function.zip"
sendgrid_api_key = "<SENDGRID_API_KEY>"
from_email       = "noreply@dev.sansmah.me"
```

> **Note:** `db_password` and `key_name` are no longer required. The DB password is auto-generated by Terraform and stored in Secrets Manager. SSH access to EC2 instances has been removed.

### demo.tfvars

Same structure as above with:
- `aws_profile = "demo"`, `environment = "demo"`
- `vpc_cidr = "10.1.0.0/16"` (and matching subnet CIDRs `10.1.x.x`)
- `route53_zone_id` from the **demo** AWS account
- `domain_name = "demo.sansmah.me"`
- `lambda_zip_path = "<path_to_lambda.zip>"`

---

## DNS Setup (Manual — done once)

Before running Terraform for the first time:

1. Register domain `sansmah.me` with a registrar (e.g., Namecheap)
2. In the **root AWS account** → Route 53 → create public hosted zone for `sansmah.me`
3. Update the registrar's nameservers to the 4 NS values from Route 53
4. In the **dev AWS account** → Route 53 → create public hosted zone for `dev.sansmah.me`
5. In the **demo AWS account** → Route 53 → create public hosted zone for `demo.sansmah.me`
6. In the **root account** hosted zone, add NS delegation records for `dev.sansmah.me` and `demo.sansmah.me`

After this one-time setup, Terraform manages all records within each subdomain's hosted zone.

---

## AMI Requirements (built via Packer in the webapp repo)

The AMI must have:
- Application installed at `/opt/csye6225/` with `csye6225` systemd service enabled
- CloudWatch Unified Agent installed at `/opt/aws/amazon-cloudwatch-agent/`
- CloudWatch agent config at `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json`
- AWS CLI v2 installed (needed by user data to fetch secret from Secrets Manager)
- `csye6225` user and group created
- Log output to `/var/log/webapp/`

User data writes `/opt/csye6225/.env` and starts both services — no credentials are embedded in the AMI.

---

## Deploy Instructions

```bash
cd aws
terraform init
terraform fmt -recursive
terraform validate

# Dev
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars

# Demo
terraform plan -var-file=demo.tfvars
terraform apply -var-file=demo.tfvars
```

After apply:
```bash
terraform output application_url   # https://dev.sansmah.me/
```

---

## Multiple Environments with Workspaces

```bash
# Create and deploy dev
terraform workspace new dev
terraform apply -var-file=dev.tfvars

# Create and deploy demo (separate state)
terraform workspace new demo
terraform apply -var-file=demo.tfvars

# Switch between environments
terraform workspace select dev
terraform workspace select demo
```

---

## Importing an SSL Certificate (Demo Environment)

For the demo environment, if you have purchased an SSL certificate from an external vendor (e.g., Namecheap), import it into ACM using the AWS CLI before running Terraform:

```bash
aws acm import-certificate \
  --certificate fileb://certificate.crt \
  --private-key fileb://private.key \
  --certificate-chain fileb://ca_bundle.crt \
  --region us-east-1 \
  --profile demo
```

The command returns a certificate ARN. Reference it in your Terraform configuration as needed.

---

## Verifying After Deploy

**HTTPS:**
```bash
curl -I https://dev.sansmah.me/healthz
# Expected: HTTP/2 200
```

**Secrets Manager:**
```bash
aws secretsmanager get-secret-value \
  --secret-id dev-db-password \
  --profile dev --region us-east-1
```

**KMS Keys:**
```bash
aws kms list-aliases --profile dev --region us-east-1 | grep dev-
```

**CloudWatch Logs:**
AWS Console → CloudWatch → Log groups → `/csye6225/dev`

---

## Cleanup

```bash
# Dev
terraform workspace select dev
terraform destroy -var-file=dev.tfvars

# Demo
terraform workspace select demo
terraform destroy -var-file=demo.tfvars
```

All resources (VPC, RDS, S3, KMS keys, Secrets Manager secrets, Lambda, DynamoDB, ASG, ALB, ACM cert, Route 53 records, IAM) are destroyed with the stack.

> **Note:** KMS keys have a 10-day deletion window after `terraform destroy`. They cannot be immediately deleted.
