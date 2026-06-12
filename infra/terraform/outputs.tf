output "c2_public_ip" {
  value       = digitalocean_droplet.c2.ipv4_address
  description = "C2 public IP — DBA beacons here, researcher management SSH"
}

output "host01_private_ip" {
  value       = digitalocean_droplet.host01.ipv4_address_private
  description = "host01 private IP within private_net VPC"
}

output "host02_private_ip" {
  value       = digitalocean_droplet.host02.ipv4_address_private
  description = "host02 private IP within private_net VPC"
}

output "host03_public_ip" {
  value       = digitalocean_droplet.host03.ipv4_address
  description = "host03 public IP — researcher SSH jump, public Flask :8080"
}

output "host03_private_ip" {
  value       = digitalocean_droplet.host03.ipv4_address_private
  description = "host03 private IP within private_net VPC"
}

output "host04_public_ip" {
  value       = digitalocean_droplet.host04.ipv4_address
  description = "host04 public IP — CI server, not visible from VPC scans"
}

output "host05_public_ip" {
  value       = digitalocean_droplet.host05.ipv4_address
  description = "host05 public IP — egress-only NAT, all inbound denied"
}
