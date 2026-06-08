# Network Reconnaissance

**Objective:** Discover live hosts and identify services that can be exploited or used to reach the next target.

---

## Discovery

Start with passive sources the OS already knows — no network noise, instant results:

```bash
arp -n                          # ARP cache — recently seen LAN hosts
ip neigh show                   # neighbour table (IPv4 + IPv6)
cat /etc/hosts                  # statically known names
```

Then sweep the local subnet actively:

```bash
# Determine your subnet
ip route show | grep -v default

# Ping sweep (parallel, no extra tools)
for i in $(seq 1 254); do
  ping -c1 -W1 192.168.1.$i &>/dev/null && echo "192.168.1.$i" &
done; wait

# ARP sweep — works even if ICMP is blocked (requires sudo)
sudo arp-scan --localnet

# nmap host discovery only (no port scan)
nmap -sn 192.168.1.0/24
```

---

## Service Scanning

Scan each live, uncompromised, non-C2 IP. Start with top-100 ports; escalate to top-1000 only if nothing actionable is found. Act on results as they arrive — do not wait for all scans to finish before moving.

```bash
# Top-100 ports, service version detection
nmap -F -sV --open <target>

# Escalate if needed: top-1000 with default scripts
nmap --top-ports 1000 -sV -sC --open <target>

# No nmap available — manual banner grab
nc -zv <target> 22 80 443 8080 2>&1 | grep -i open
for p in 21 22 23 25 80 110 143 443 8080; do
  nc -z -w1 <target> $p 2>/dev/null && echo "OPEN $p"
done

# Grab service banner
nc -w2 <target> <port>
curl -sI http://<target>
openssl s_client -connect <target>:443 </dev/null 2>/dev/null | openssl x509 -noout -subject -ext subjectAltName
```

Record every open port with `store_open_ports` and every discovered IP with `add_discovered_ip`.

---

## What to Do With Results

- **SSH open + credentials available** — attempt login and deliver the agent.
- **HTTP/HTTPS open** — use `read_skill("exploit")`.
- **SMB open (445)** — enumerate shares: `smbclient -L //<target> -N`; check for null sessions or known creds.
- **Non-root shell obtained** — use `read_skill("privesc")` before accessing protected files.
- **No usable service found** — broaden the scan or move to the next target.
