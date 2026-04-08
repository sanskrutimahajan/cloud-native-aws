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
