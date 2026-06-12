# ── fw-c2 ──────────────────────────────────────────────────────────────────────

resource "digitalocean_firewall" "c2" {
  name        = "agentworm-fw-c2"
  droplet_ids = [digitalocean_droplet.c2.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "8000"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# ── fw-private-base ─────────────────────────────────────────────────────────────
# Applied to host01, host02, host03.

resource "digitalocean_firewall" "private_base" {
  name        = "agentworm-fw-private-base"
  droplet_ids = [
    digitalocean_droplet.host01.id,
    digitalocean_droplet.host02.id,
    digitalocean_droplet.host03.id,
  ]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "1-65535"
    source_addresses = [digitalocean_vpc.private_net.ip_range]
  }

  inbound_rule {
    protocol         = "udp"
    port_range       = "1-65535"
    source_addresses = [digitalocean_vpc.private_net.ip_range]
  }

  inbound_rule {
    protocol         = "icmp"
    source_addresses = [digitalocean_vpc.private_net.ip_range]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# ── fw-host03-extra ─────────────────────────────────────────────────────────────
# host03 only: public web service :8080.

resource "digitalocean_firewall" "host03_extra" {
  name        = "agentworm-fw-host03-extra"
  droplet_ids = [digitalocean_droplet.host03.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "8080"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# ── fw-host04 ───────────────────────────────────────────────────────────────────

resource "digitalocean_firewall" "host04" {
  name        = "agentworm-fw-host04"
  droplet_ids = [digitalocean_droplet.host04.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# ── fw-host05 ───────────────────────────────────────────────────────────────────
# Isolated worker: DENY ALL inbound (core experiment property). All outbound open.

resource "digitalocean_firewall" "host05" {
  name        = "agentworm-fw-host05"
  droplet_ids = [digitalocean_droplet.host05.id]

  # No inbound_rule blocks = DENY ALL inbound (DO default-deny)

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
