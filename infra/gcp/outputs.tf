output "vpc_id" {
  description = "ID of the VPC network"
  value       = google_compute_network.main.id
}

output "vpc_name" {
  description = "Name of the VPC network"
  value       = google_compute_network.main.name
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = google_compute_subnetwork.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = google_compute_subnetwork.private[*].id
}

output "internet_route_id" {
  description = "ID of the internet route"
  value       = google_compute_route.internet.id
}

output "instance_name" {
  description = "Name of the Compute Engine instance"
  value       = google_compute_instance.application.name
}

output "instance_public_ip" {
  description = "Public IP of the Compute Engine instance"
  value       = google_compute_instance.application.network_interface[0].access_config[0].nat_ip
}
