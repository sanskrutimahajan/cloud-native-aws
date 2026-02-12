# tf-infra

Infrastructure as Code - Terraform configurations for AWS and GCP networking.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.0
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with `dev` and `demo` profiles
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) configured with application default credentials

## Repository Structure

```
tf-infra/
├── .github/workflows/
│   └── terraform-ci.yml        # CI: fmt, init, validate for AWS & GCP
├── aws/
│   ├── main.tf                 # VPC, subnets, route tables, security groups
│   ├── variables.tf            # Input variable declarations
│   ├── outputs.tf              # Output value declarations
│   ├── providers.tf            # AWS provider configuration
│   ├── dev.tfvars              # Dev environment values (not committed)
│   ├── demo.tfvars             # Demo environment values (not committed)
│   └── terraform.tfvars.example
└── gcp/
    ├── main.tf                 # VPC, subnets, routes, firewall rules
    ├── variables.tf
    ├── outputs.tf
    ├── providers.tf
    ├── dev.tfvars              # Dev environment values (not committed)
    ├── demo.tfvars             # Demo environment values (not committed)
    └── terraform.tfvars.example
```

## Setup Instructions

### AWS

```bash
cd aws
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=demo.tfvars
terraform apply -var-file=demo.tfvars
```

### GCP

```bash
cd gcp
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan -var-file=demo.tfvars
terraform apply -var-file=demo.tfvars
```

## What Gets Created

### AWS Resources
- VPC with DNS support enabled
- 3 public subnets across 3 availability zones
- 3 private subnets across 3 availability zones
- Internet Gateway attached to the VPC
- Public route table with internet route (0.0.0.0/0 → IGW)
- Private route table
- Application security group (HTTP, HTTPS, SSH, app port)
- Database security group (DB port from application SG only)

### GCP Resources
- VPC network with custom subnet mode
- 3 public subnets across 3 zones
- 3 private subnets across 3 zones with private Google access
- Internet route (0.0.0.0/0 → default internet gateway)
- Firewall rule allowing TCP on ports 22, 80, 443 for tagged instances
- Deny-all firewall rule at lower priority

## Multiple Environments

Two tfvars files (`dev.tfvars` and `demo.tfvars`) allow switching environments without editing files. Each uses different CIDR ranges so both can coexist.

```bash
# Demo environment
terraform plan -var-file=demo.tfvars

# Dev environment
terraform plan -var-file=dev.tfvars
```

## Cleanup

```bash
terraform destroy -var-file=demo.tfvars
```
