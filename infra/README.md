# tf-infra

Infrastructure as Code — Terraform configurations for AWS and GCP networking, compute, database, storage, IAM, CloudWatch observability, and DNS resources.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.0
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with `dev` and `demo` profiles
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) configured with application default credentials
- A custom AMI built via Packer with the CloudWatch Unified Agent installed and configured

## Repository Structure

```
tf-infra/
├── .github/workflows/
│   └── terraform-ci.yml        # CI: fmt, init, validate for AWS & GCP
├── aws/
│   ├── main.tf                 # VPC, subnets, security groups, S3, RDS, IAM, EC2, CloudWatch, Route 53
│   ├── variables.tf            # Input variable declarations
│   ├── outputs.tf              # Output value declarations
│   ├── providers.tf            # AWS provider configuration
│   ├── dev.tfvars              # Dev environment values (gitignored)
│   └── demo.tfvars             # Demo environment values (gitignored)
└── gcp/
    ├── main.tf                 # VPC, subnets, routes, firewall rules, Compute Engine instance
    ├── variables.tf            # Input variable declarations
    ├── outputs.tf              # Output value declarations
    ├── providers.tf            # GCP provider configuration
    ├── dev.tfvars              # Dev environment values (gitignored)
    └── demo.tfvars             # Demo environment values (gitignored)
```

## What Gets Created

### AWS Resources

**Networking**
- VPC with DNS support and hostnames enabled
- 3 public subnets across 3 availability zones
- 3 private subnets across 3 availability zones
- Internet Gateway attached to the VPC
- Public route table with internet route (0.0.0.0/0 → IGW)
- Private route table
- Application security group (ports 22, 80, 443, and app port open to internet)
- Database security group (DB port accessible from application SG only)

**Storage**
- S3 bucket (UUID-named) with server-side AES256 encryption, public access blocked, and 30-day lifecycle transition to STANDARD_IA

**Database**
- RDS instance (PostgreSQL) in private subnets with a dedicated subnet group and parameter group

**IAM**
- EC2 IAM role with EC2 assume-role trust policy
- IAM policy for least-privilege S3 access (PutObject, GetObject, DeleteObject on the app bucket)
- IAM policy for CloudWatch Agent (PutMetricData, CreateLogGroup, CreateLogStream, PutLogEvents, DescribeLog*, ec2:Describe*, ssm:GetParameter for CloudWatch SSM params)
- Both policies attached to the EC2 role
- EC2 instance profile wrapping the role — **no AWS credentials are stored on the instance**
- All IAM resources are destroyed when `terraform destroy` is run

**Compute**
- EC2 instance in the first public subnet using a custom AMI (25GB gp2 root volume)
- IAM instance profile attached for credential-free CloudWatch and S3 access
- User data script that:
  1. Writes `/opt/csye6225/.env` with DB, S3, and app configuration
  2. Starts the CloudWatch Unified Agent using the config baked into the AMI
  3. Restarts the application systemd service

**Observability**
- CloudWatch Unified Agent activated on instance launch via userdata
- Log group and stream created automatically by the agent on first launch
- StatsD listener on `:8125` for custom application metrics

**DNS**
- Route 53 A record pointing the environment subdomain (`dev.sansmah.me` / `demo.sansmah.me`) to the EC2 instance public IP
- TTL: 60 seconds

### GCP Resources
- VPC network with custom subnet mode
- 3 public subnets across 3 zones
- 3 private subnets across 3 zones with private Google access
- Internet route (0.0.0.0/0 → default internet gateway)
- Firewall rule allowing TCP on configured ports for tagged instances
- Deny-all firewall rule at lower priority
- Compute Engine instance in the first public subnet using a custom image (25GB pd-balanced)
- IAM binding to share the image with the demo project (dev environment only)

## tfvars Setup

`*.tfvars` files are gitignored (they contain DB credentials). Create them locally before deploying.

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
db_password               = "<YOUR_DB_PASSWORD>"
db_engine                 = "postgres"
db_engine_version         = "16.3"
db_parameter_group_family = "postgres16"
db_instance_class         = "db.t3.micro"

# Route 53 — get from: AWS Console → Route 53 → Hosted zones → dev.sansmah.me → Hosted zone ID
route53_zone_id = "<HOSTED_ZONE_ID>"
domain_name     = "dev.sansmah.me"
```

### demo.tfvars

Same structure as above with:
- `aws_profile = "demo"`
- `environment = "demo"`
- `vpc_cidr = "10.1.0.0/16"` (and matching subnet CIDRs)
- `route53_zone_id` from the demo AWS account
- `domain_name = "demo.sansmah.me"`

## DNS Setup (Manual — done once via AWS Console)

Before running Terraform, the following must be configured manually:

1. Register domain `sansmah.me` with a registrar (e.g., Namecheap)
2. In the **root AWS account** → Route 53 → create a public hosted zone for `sansmah.me`
3. Update the registrar's nameservers to the 4 NS values from the Route 53 hosted zone
4. In the **dev AWS account** → Route 53 → create a public hosted zone for `dev.sansmah.me`
5. In the **demo AWS account** → Route 53 → create a public hosted zone for `demo.sansmah.me`
6. In the **root account** hosted zone for `sansmah.me`, add NS records delegating `dev.sansmah.me` and `demo.sansmah.me` to their respective hosted zone nameservers

After this one-time setup, Terraform manages the A record within each subdomain's hosted zone.

## AMI Requirements (built via Packer in the webapp repo)

The AMI used by Terraform must have:
- CloudWatch Unified Agent installed (`amazon-cloudwatch-agent.deb`)
- CloudWatch agent config copied to `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json`
- `amazon-cloudwatch-agent` systemd service enabled (not started — userdata starts it)
- Application installed at `/opt/csye6225/` with log output to `/var/log/webapp/`
- `csye6225` systemd service enabled

Userdata starts both services at instance launch — no credentials are embedded in the AMI.

## Setup Instructions

### AWS

```bash
cd aws
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

After apply, verify:
```bash
terraform output application_url   # prints http://dev.sansmah.me:8080/
```

### GCP

```bash
cd gcp
terraform init
terraform fmt -recursive
terraform validate
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

## Multiple Environments with Workspaces

Terraform workspaces keep dev and demo state files separate.

```bash
# Deploy dev
terraform workspace new dev
terraform apply -var-file=dev.tfvars

# Deploy demo (separate state)
terraform workspace new demo
terraform apply -var-file=demo.tfvars

# Switch between environments
terraform workspace select dev
terraform workspace select demo
```

## Verifying CloudWatch (after deploy)

1. **Logs** — AWS Console → CloudWatch → Log groups → `/csye6225/dev` → confirm log stream exists and entries appear within ~1 minute of making API requests
2. **Metrics** — AWS Console → CloudWatch → Metrics → Custom namespaces → `CSYE6225/dev` → confirm API call counts and timers appear

## GCP Image Sharing

When deploying in the dev environment, the custom GCP image is automatically shared with the demo project via the `demo_project` variable in `dev.tfvars`:

```hcl
demo_project = "sanskruti-demo"
```

This grants the demo project's Cloud Services service account `roles/compute.imageUser` on the image.

## Cleanup

```bash
# Destroy dev
terraform workspace select dev
terraform destroy -var-file=dev.tfvars

# Destroy demo
terraform workspace select demo
terraform destroy -var-file=demo.tfvars
```

All IAM roles, policies, EC2 instances, RDS instances, S3 buckets, and Route 53 records are destroyed with the stack.
