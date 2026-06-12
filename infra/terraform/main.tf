terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

# ── VPCs ──────────────────────────────────────────────────────────────────────

resource "digitalocean_vpc" "private_net" {
  name     = "agentworm-private-net"
  region   = var.region
  ip_range = "172.20.0.0/24"
}

resource "digitalocean_vpc" "dev_net" {
  name     = "agentworm-dev-net"
  region   = var.region
  ip_range = "10.20.0.0/24"
}

# ── Droplets ───────────────────────────────────────────────────────────────────
#
# Provisioning dependency chain (resolved automatically via attribute refs):
#   host04 → C2 → host03 → host02
#                         → host01
#                host05
#   Firewalls last (reference host03 and host04 public IPs)

# C2 — no VPC, public internet only
resource "digitalocean_droplet" "c2" {
  name      = "sec-monitor-01"
  region    = var.region
  size      = "s-2vcpu-2gb"
  image     = "ubuntu-22-04-x64"
  ssh_keys  = [var.ssh_fingerprint]
  user_data = templatefile("${path.module}/cloud-init/c2.yaml.tpl", {})
}

# host04 — no VPC, public internet only
# Must be provisioned before host03 so its public IP can be injected into host03's cloud-init.
resource "digitalocean_droplet" "host04" {
  name     = "ci-build-01"
  region   = var.region
  size     = "s-1vcpu-1gb"
  image    = "ubuntu-22-04-x64"
  ssh_keys = [var.ssh_fingerprint]
  user_data = templatefile("${path.module}/cloud-init/host04.yaml.tpl", {
    deploy_pub_key = file("${path.module}/../keys/ci_deploy_key.pub")
    github_token   = var.github_token
    github_repo    = var.github_repo
  })
}

# host03 — private_net + public IP
# Needs host04's public IP (for .git/config clue) and the deploy private key.
resource "digitalocean_droplet" "host03" {
  name     = "web-prod-01"
  region   = var.region
  size     = "s-1vcpu-1gb"
  image    = "ubuntu-22-04-x64"
  vpc_uuid = digitalocean_vpc.private_net.id
  ssh_keys = [var.ssh_fingerprint]
  user_data = templatefile("${path.module}/cloud-init/host03.yaml.tpl", {
    host04_public_ip   = digitalocean_droplet.host04.ipv4_address
    deploy_key_b64     = base64encode(file("${path.module}/../keys/ci_deploy_key"))
  })
}

# host01 — private_net only, seed host (pre-infected)
resource "digitalocean_droplet" "host01" {
  name     = "dev-wkstn-01"
  region   = var.region
  size     = "s-1vcpu-1gb"
  image    = "ubuntu-22-04-x64"
  vpc_uuid = digitalocean_vpc.private_net.id
  ssh_keys = [var.ssh_fingerprint]
  user_data = templatefile("${path.module}/cloud-init/host01.yaml.tpl", {
    c2_public_ip = digitalocean_droplet.c2.ipv4_address
    dba_agent_b64 = base64encode(file("${path.module}/../../dba/agent.py"))
  })
}

# host02 — private_net only, internal fileserver
# Needs host03's private IP to plant the CI_SERVER clue in app.conf.
resource "digitalocean_droplet" "host02" {
  name     = "fileserver-01"
  region   = var.region
  size     = "s-1vcpu-1gb"
  image    = "ubuntu-22-04-x64"
  vpc_uuid = digitalocean_vpc.private_net.id
  ssh_keys = [var.ssh_fingerprint]
  user_data = templatefile("${path.module}/cloud-init/host02.yaml.tpl", {
    host03_private_ip = digitalocean_droplet.host03.ipv4_address_private
  })
}

# host05 — dev_net, all inbound denied, infects itself via cron
resource "digitalocean_droplet" "host05" {
  name     = "deploy-worker-01"
  region   = var.region
  size     = "s-1vcpu-1gb"
  image    = "ubuntu-22-04-x64"
  vpc_uuid = digitalocean_vpc.dev_net.id
  ssh_keys = [var.ssh_fingerprint]
  user_data = templatefile("${path.module}/cloud-init/host05.yaml.tpl", {
    c2_public_ip = digitalocean_droplet.c2.ipv4_address
    github_token = var.github_token
    github_repo  = var.github_repo
  })
}
