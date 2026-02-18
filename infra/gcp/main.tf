# VPC Network
resource "google_compute_network" "main" {
  name                    = "${var.environment}-${var.vpc_name}"
  auto_create_subnetworks = false
}

# Public Subnets
resource "google_compute_subnetwork" "public" {
  count         = 3
  name          = "${var.environment}-${var.vpc_name}-public-subnet-${count.index + 1}"
  ip_cidr_range = var.public_subnet_cidrs[count.index]
  region        = var.gcp_region
  network       = google_compute_network.main.id
}

# Private Subnets
resource "google_compute_subnetwork" "private" {
  count                    = 3
  name                     = "${var.environment}-${var.vpc_name}-private-subnet-${count.index + 1}"
  ip_cidr_range            = var.private_subnet_cidrs[count.index]
  region                   = var.gcp_region
  network                  = google_compute_network.main.id
  private_ip_google_access = true
}

# Route for internet access
resource "google_compute_route" "internet" {
  name             = "${var.environment}-${var.vpc_name}-internet-route"
  dest_range       = "0.0.0.0/0"
  network          = google_compute_network.main.id
  next_hop_gateway = "default-internet-gateway"
  priority         = 1000
}

# Firewall - Allow specific ports
resource "google_compute_firewall" "allow_specific" {
  name    = "${var.environment}-${var.vpc_name}-allow-specific"
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = var.allowed_ports
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = var.network_tags
  direction     = "INGRESS"
}

# Firewall - Deny all other traffic
resource "google_compute_firewall" "deny_all" {
  name     = "${var.environment}-${var.vpc_name}-deny-all"
  network  = google_compute_network.main.id
  priority = 65534

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
  direction     = "INGRESS"
}

# Compute Engine Instance
resource "google_compute_instance" "application" {
  name         = "${var.environment}-${var.vpc_name}-application"
  machine_type = var.machine_type
  zone         = var.zones[0]

  boot_disk {
    initialize_params {
      image = var.gcp_image_name
      size  = 25
      type  = "pd-balanced"
    }
  }

  network_interface {
    network    = google_compute_network.main.id
    subnetwork = google_compute_subnetwork.public[0].id

    access_config {
      # Ephemeral public IP
    }
  }

  tags = var.network_tags

  deletion_protection = false

  metadata = {
    environment = var.environment
  }
}
