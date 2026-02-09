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
