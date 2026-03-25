variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile to use"
  type        = string
  default     = "dev"
}

variable "environment" {
  description = "Environment name (dev or demo)"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "vpc_name" {
  description = "Name tag for VPC"
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

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "application_port" {
  description = "Port the application runs on"
  type        = number
  default     = 8080
}

variable "database_port" {
  description = "Database port"
  type        = number
  default     = 5432
}

variable "ami_id" {
  description = "Custom AMI ID for the EC2 instance"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}

variable "key_name" {
  description = "SSH key pair name for EC2 instances"
  type        = string
}

variable "db_identifier" {
  description = "RDS instance identifier"
  type        = string
  default     = "csye6225"
}

variable "db_name" {
  description = "Name of the database"
  type        = string
  default     = "csye6225"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "csye6225"
}

variable "db_password" {
  description = "Master password for the RDS instance"
  type        = string
  sensitive   = true
}

variable "db_engine" {
  description = "Database engine (postgres, mysql, or mariadb)"
  type        = string
  default     = "postgres"
}

variable "db_engine_version" {
  description = "Database engine version"
  type        = string
  default     = "16"
}

variable "db_parameter_group_family" {
  description = "DB parameter group family (e.g., postgres16, mysql8.0, mariadb10.11)"
  type        = string
  default     = "postgres16"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "route53_zone_id" {
  description = "Route 53 hosted zone ID for the subdomain (e.g., dev.sansmah.me)"
  type        = string
}

variable "domain_name" {
  description = "Fully qualified domain name for the application (e.g., dev.sansmah.me)"
  type        = string
}
