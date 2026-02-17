packer {
  required_plugins {
    amazon = {
      version = ">= 1.2.0"
      source  = "github.com/hashicorp/amazon"
    }
    googlecompute = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/googlecompute"
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

# GCP Image Builder
source "googlecompute" "webapp" {
  project_id              = var.gcp_project_id
  zone                    = var.gcp_zone
  machine_type            = var.gcp_machine_type
  source_image_family     = "ubuntu-2404-lts-amd64"
  source_image_project_id = ["ubuntu-os-cloud"]
  image_name              = local.image_name
  image_description       = "Custom image for CSYE 6225 web application"
  image_family            = "csye6225-webapp"
  ssh_username            = var.ssh_username
  disk_size               = 25
  disk_type               = "pd-balanced"
}

build {
  sources = [
    "source.amazon-ebs.webapp",
    "source.googlecompute.webapp",
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

  # Share GCP image with demo project
  post-processor "shell-local" {
    only = ["googlecompute.webapp"]
    inline = [
      "DEMO_PROJECT_NUM=$(gcloud projects describe ${var.gcp_image_users[0]} --format='value(projectNumber)')",
      "gcloud compute images add-iam-policy-binding ${local.image_name} --project=${var.gcp_project_id} --member=\"serviceAccount:$${DEMO_PROJECT_NUM}@cloudservices.gserviceaccount.com\" --role='roles/compute.imageUser'"
    ]
  }
}
