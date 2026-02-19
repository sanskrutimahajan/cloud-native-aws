# tf-infra

Infrastructure as Code - Terraform configurations for AWS and GCP networking and compute resources.

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
│   ├── main.tf                 # VPC, subnets, route tables, security groups, EC2 instance
│   ├── variables.tf            # Input variable declarations
│   ├── outputs.tf              # Output value declarations
│   ├── providers.tf            # AWS provider configuration
│   ├── dev.tfvars              # Dev environment values (not committed)
│   ├── demo.tfvars             # Demo environment values (not committed)
│   └── terraform.tfvars.example
└── gcp/
    ├── main.tf                 # VPC, subnets, routes, firewall rules, Compute Engine instance
    ├── variables.tf            # Input variable declarations
    ├── outputs.tf              # Output value declarations
    ├── providers.tf            # GCP provider configuration
    ├── dev.tfvars              # Dev environment values (not committed)
    ├── demo.tfvars             # Demo environment values (not committed)
    └── terraform.tfvars.example
```

## What Gets Created

### AWS Resources
- VPC with DNS support and hostnames enabled
- 3 public subnets across 3 availability zones
- 3 private subnets across 3 availability zones
- Internet Gateway attached to the VPC
- Public route table with internet route (0.0.0.0/0 → IGW)
- Private route table
- Application security group (ports 22, 80, 443, and app port from anywhere)
- Database security group (DB port from application SG only)
- EC2 instance in the first public subnet using a custom AMI (25GB gp2 volume)

### GCP Resources
- VPC network with custom subnet mode
- 3 public subnets across 3 zones
- 3 private subnets across 3 zones with private Google access
- Internet route (0.0.0.0/0 → default internet gateway)
- Firewall rule allowing TCP on configured ports for tagged instances
- Deny-all firewall rule at lower priority
- Compute Engine instance in the first public subnet using a custom image (25GB pd-balanced)
- IAM binding to share the image with the demo project (dev environment only)

## Setup Instructions

### AWS

```bash
cd aws
terraform init
terraform workspace new dev   # or: terraform workspace select dev
terraform fmt -recursive
terraform validate
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

### GCP

```bash
cd gcp
terraform init
terraform workspace new dev   # or: terraform workspace select dev
terraform fmt -recursive
terraform validate
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

## Multiple Environments with Workspaces

Terraform workspaces keep dev and demo state files separate, allowing both environments to exist independently.

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

## GCP Image Sharing

When deploying in the dev environment, the custom GCP image is automatically shared with the demo project. This is handled via the `demo_project` variable in `dev.tfvars`:

```hcl
demo_project = "sanskruti-demo"
```

This grants the demo project's Cloud Services service account `roles/compute.imageUser` on the image, so `terraform apply -var-file=demo.tfvars` can use the same image without manual sharing.

## Cleanup

```bash
# Destroy dev
terraform workspace select dev
terraform destroy -var-file=dev.tfvars

# Destroy demo
terraform workspace select demo
terraform destroy -var-file=demo.tfvars
```
