# Cloud-Native Web Application on AWS

**Secure, auto-scaling web app on AWS: FastAPI, Terraform, Packer, Lambda, and GitHub Actions CI/CD.**

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-7B42BC?logo=terraform&logoColor=white)
![Packer](https://img.shields.io/badge/Packer-02A8EF?logo=packer&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-232F3E?logo=amazonwebservices&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)

An end-to-end cloud-native system built for **CSYE 6225 — Network Structures & Cloud Computing** (Northeastern University). It covers the full lifecycle of a production-style service: a REST API, immutable machine images built with Packer, AWS infrastructure defined in Terraform, an event-driven Lambda function, and CI/CD with GitHub Actions.

This monorepo combines three repositories that were originally developed separately. Each one keeps its **full commit history** in its own folder.

| Folder | What it is | Stack |
|---|---|---|
| [`webapp/`](webapp/) | REST API for users, a course catalog, and syllabus file storage, plus the Packer template that bakes it into an AMI | Python, FastAPI, PostgreSQL, SQLAlchemy, boto3, Packer |
| [`infra/`](infra/) | Infrastructure as Code for the whole AWS environment (networking, compute, database, storage, security, DNS, TLS, serverless) | Terraform, AWS |
| [`serverless/`](serverless/) | Email-verification function triggered when a new user signs up | AWS Lambda (Python 3.12), SNS, DynamoDB, SendGrid |

## Architecture

![Architecture diagram: users reach an HTTPS load balancer in front of an EC2 Auto Scaling group in a multi-AZ VPC, backed by RDS, S3, KMS and Secrets Manager; sign-ups flow through SNS to a Lambda that emails via SendGrid; GitHub Actions and Packer build new AMIs rolled out by instance refresh](docs/architecture.svg)

### How the pieces fit together

1. **Build:** `webapp-packer-build` (originally triggered on every merged PR) runs the integration tests, zips the app, and uses **Packer** to bake an Ubuntu 24.04 AMI with the app, a `systemd` service, and the CloudWatch Agent preinstalled ([`webapp/packer/`](webapp/packer/), [`webapp/scripts/setup.sh`](webapp/scripts/setup.sh)).
2. **Provision:** **Terraform** ([`infra/aws/`](infra/aws/)) creates the VPC, security groups, ALB, Auto Scaling group, RDS, S3, KMS keys, Secrets Manager secrets, Route 53 records, ACM certificate, SNS topic, DynamoDB table, and Lambda function. EC2 instances launch from the Packer AMI, and user data pulls the database password from Secrets Manager at boot. No credentials are baked into the image.
3. **Deploy:** the build workflow creates a new launch template version with the fresh AMI and starts an **instance refresh**, which rolls the Auto Scaling group onto the new image with no downtime.
4. **Run:** the API stores data in RDS and syllabus files in S3, and ships logs and custom metrics (API latency, DB and S3 timings) to CloudWatch. When a user signs up, it publishes to **SNS**. That triggers the **Lambda** function, which emails a verification link through SendGrid and records the send in DynamoDB to avoid duplicates. The user clicks the link, which hits `GET /v1/validateEmail`.

## Highlights

- **Security by default:** customer-managed KMS keys with rotation for EBS, RDS, S3, and Secrets Manager. Least-privilege IAM roles, no SSH access to instances, no static AWS keys on hosts, a TLS 1.3 ALB policy, and BCrypt password hashing.
- **High availability and scaling:** three availability zones, an ALB health check on `/healthz`, and CPU-based scale-up/scale-down policies.
- **Immutable infrastructure:** every release is a new AMI rolled out with an instance refresh, not patched in place.
- **Observability:** application logs go to CloudWatch Logs, and StatsD counters and timers go to CloudWatch Metrics.
- **Tested:** an integration test suite (~160 test functions) runs against a real PostgreSQL service container in CI. S3 and metrics calls are mocked.
- **Multi-environment:** separate `dev` and `demo` AWS accounts, each with its own Route 53 subdomain and Terraform workspace.

## Repository layout

```
.
├── .github/workflows/        # all CI/CD (see below)
├── webapp/
│   ├── app/                  # FastAPI application (routes, models, S3, SNS, metrics)
│   ├── tests/                # integration tests (pytest)
│   ├── packer/               # AMI template + variables
│   ├── scripts/setup.sh      # provisioning script run by Packer
│   └── cloudwatch-config.json
├── infra/
│   ├── aws/                  # Terraform for the AWS environment
│   └── gcp/                  # Terraform for an earlier GCP setup (VPC, firewall, VM)
└── serverless/
    └── lambda_function.py    # SNS-triggered email verification handler
```

## CI/CD

All workflows live in [`.github/workflows/`](.github/workflows/). Each one only watches its own folder (`paths:` filter) and runs from that folder (`defaults.run.working-directory`).

| Workflow | Trigger | What it does |
|---|---|---|
| `webapp-ci.yml` | Pull request touching `webapp/` | Runs the integration tests against PostgreSQL 16 |
| `webapp-packer-validate.yml` | Pull request touching `webapp/` | `packer fmt -check` and `packer validate` |
| `webapp-packer-build.yml` | Manual (`workflow_dispatch`) | Tests, AMI build, launch template update, ASG instance refresh |
| `infra-terraform-ci.yml` | Pull request touching `infra/aws` or `infra/gcp` | `terraform fmt -check`, `init`, and `validate` |
| `serverless-deploy.yml` | Manual (`workflow_dispatch`) | Zips and deploys the Lambda function code |

> The two deployment workflows were automatic in the original repos: on PR merge and on push to `main`. They are manual here because they need AWS credentials (repository secrets) that aren't configured in this repo. Each file has a comment showing the original trigger, so automatic runs can be restored.

## Getting started

Each folder has its own detailed README:

- **[webapp/README.md](webapp/README.md):** local setup, environment variables, full API reference, testing, logging and metrics
- **[infra/README.md](infra/README.md):** what Terraform creates, `tfvars` setup, DNS delegation, deploy, verify, and cleanup steps
- **[serverless/README.md](serverless/README.md):** Lambda packaging, environment variables, SNS message format, duplicate prevention

Quick local run of the API:

```bash
git clone https://github.com/sanskrutimahajan/cloud-native-aws.git
cd cloud-native-aws/webapp
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# create a .env with DATABASE_* settings (see webapp/README.md)
python run.py            # http://localhost:8080/healthz
pytest -v                # run the test suite (needs a local PostgreSQL)
```

## Security note

No secrets are stored in this repository. `*.tfvars`, `.env`, and Terraform state files are gitignored, and only `*.tfvars.example` templates with placeholder values are committed. The full history was scanned with gitleaks before publishing.
