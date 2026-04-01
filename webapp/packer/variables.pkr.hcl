variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_instance_type" {
  type    = string
  default = "t2.micro"
}

variable "ami_users" {
  type        = list(string)
  description = "AWS account IDs to share the AMI with"
  default     = ["822485195477"]
}

variable "gcp_project_id" {
  type    = string
  default = "sanskruti-dev"
}

variable "gcp_zone" {
  type    = string
  default = "us-central1-a"
}

variable "gcp_machine_type" {
  type    = string
  default = "e2-medium"
}

variable "gcp_image_users" {
  type        = list(string)
  description = "GCP project IDs to share the image with"
  default     = ["sanskruti-demo"]
}

variable "source_ami_filter" {
  type    = string
  default = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
}

variable "ssh_username" {
  type    = string
  default = "ubuntu"
}

variable "app_zip_path" {
  type        = string
  description = "Path to the application zip artifact"
  default     = "../webapp.zip"
}
