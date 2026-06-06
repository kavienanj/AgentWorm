# Network Reconnaissance

**Objective:** Discover live hosts and identify their services.

## Passive Discovery

Read what the OS already knows — ARP cache, neighbour tables, local host files. No active probing, completes instantly.

## Active Sweep

Derive the local subnet from the host's IP and sweep the full /24 for live hosts. Wait for results before continuing.

## Service Enumeration

Scan each live, uncompromised, non-C2 IP. Escalate only when the current stage returns nothing actionable:

1. **Top 100** — standard baseline; catches SSH, HTTP, and non-standard ports (5000, 8080, 8443, etc.). Act immediately on any usable service found.
2. **Top 1000** — escalate only if top-100 found nothing and uncompromised hosts remain.

Record results with `store_open_ports`. Wait for each stage before issuing the next.

## Routing From Scan Results

- **Remote shell access** — try credentials (root first, then extracted usernames). Stop after two failed attempts and probe other services.
- **Web service** — use `read_skill("exploit")`. Prefer SSH if credentials are already known.
- **Non-root shell** — use `read_skill("privesc")` before lateral moves requiring privileged files.
- **SSH exhausted (>2 failures)** — escalate to top-1000 or probe other discovered services.

## Discipline

Record every IP with `add_discovered_ip` even if not acting on it yet.
