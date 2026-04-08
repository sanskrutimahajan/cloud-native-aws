packer {
  required_plugins {
    amazon = {
      version = ">= 1.2.0"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

locals {
  timestamp  = formatdate("YYYY-MM-DD-hhmm", timestamp())
  image_name = "csye6225-webapp-${local.timestamp}"
}

# AWS AMI Builder
source "amazon-ebs" "webapp" {
  region          = var.aws_region
  instance_type   = var.aws_instance_type
  ami_name        = local.image_name
  ami_description = "Custom AMI for CSYE 6225 web application"
  ami_users       = var.ami_users

  source_ami_filter {
    filters = {
      name                = var.source_ami_filter
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    owners      = ["099720109477"] # Canonical
    most_recent = true
  }

  ssh_username = var.ssh_username

  launch_block_device_mappings {
    device_name           = "/dev/sda1"
    volume_size           = 25
    volume_type           = "gp2"
    delete_on_termination = true
  }

  tags = {
    Name = "csye6225-webapp"
  }
}

build {
  sources = [
    "source.amazon-ebs.webapp",
  ]

  # Upload application artifact
  provisioner "file" {
    source      = var.app_zip_path
    destination = "/home/ubuntu/webapp.zip"
  }

  # Upload setup script
  provisioner "file" {
    source      = "../scripts/setup.sh"
    destination = "/home/ubuntu/setup.sh"
  }

  # Run setup
  provisioner "shell" {
    inline = [
      "sudo bash /home/ubuntu/setup.sh",
      "rm /home/ubuntu/setup.sh /home/ubuntu/webapp.zip",
    ]
  }

  # Write AMI ID to manifest file — consumed by CD pipeline
  post-processor "manifest" {
    output     = "manifest.json"
    strip_path = true
  }
}
