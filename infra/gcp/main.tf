# VPC Network
resource "google_compute_network" "main" {
  name                    = var.vpc_name
  auto_create_subnetworks = false
}

# Public Subnets
resource "google_compute_subnetwork" "public" {
  count         = 3
  name          = "${var.vpc_name}-public-subnet-${count.index + 1}"
  ip_cidr_range = var.public_subnet_cidrs[count.index]
  region        = var.gcp_region
  network       = google_compute_network.main.id
}

# Private Subnets
resource "google_compute_subnetwork" "private" {
  count                    = 3
  name                     = "${var.vpc_name}-private-subnet-${count.index + 1}"
  ip_cidr_range            = var.private_subnet_cidrs[count.index]
  region                   = var.gcp_region
  network                  = google_compute_network.main.id
  private_ip_google_access = true
}

# Route for internet access
resource "google_compute_route" "internet" {
  name             = "${var.vpc_name}-internet-route"
  dest_range       = "0.0.0.0/0"
  network          = google_compute_network.main.id
  next_hop_gateway = "default-internet-gateway"
  priority         = 1000
}

# Firewall - Allow specific ports
resource "google_compute_firewall" "allow_specific" {
  name    = "${var.vpc_name}-allow-specific"
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = var.allowed_ports
  }

  source_ranges = ["0.0.0.0/0"]
  direction     = "INGRESS"
}

# Firewall - Deny all other traffic
resource "google_compute_firewall" "deny_all" {
  name     = "${var.vpc_name}-deny-all"
  network  = google_compute_network.main.id
  priority = 65534

  deny {
    protocol = "all"
  }

  source_ranges = ["0.0.0.0/0"]
  direction     = "INGRESS"
}
