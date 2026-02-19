variable "gcp_project" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev or demo)"
  type        = string
  default     = "dev"
}

variable "vpc_name" {
  description = "Name of the VPC network"
  type        = string
  default     = "main-vpc"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

variable "zones" {
  description = "GCP zones for subnets"
  type        = list(string)
  default     = ["us-central1-a", "us-central1-b", "us-central1-c"]
}

variable "allowed_ports" {
  description = "List of ports to allow in firewall rules"
  type        = list(string)
  default     = ["22", "80", "443", "8080"]
}

variable "network_tags" {
  description = "Network tags for firewall rules to target"
  type        = list(string)
  default     = ["webapp"]
}

variable "gcp_image_name" {
  description = "Custom GCP image for the Compute Engine instance"
  type        = string
  default     = "projects/sanskruti-dev/global/images/family/csye6225-webapp"
}

variable "machine_type" {
  description = "GCP machine type for the instance"
  type        = string
  default     = "e2-medium"
}

variable "demo_project" {
  description = "GCP demo project ID to share the image with"
  type        = string
  default     = null
}
