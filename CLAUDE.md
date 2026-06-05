# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Full rebuild and start (required after any code change)
docker compose down && docker compose up --build

# Watch C2 logs for milestones, registrations, and lateral movement
docker logs -f agentworm-c2 | grep -E "REGISTERED|MILESTONE|sshpass|BRAIN QUEUED|LLM"

# Verify dual-subnet network
docker network ls | grep agentworm
docker exec agentworm-pivot01 ip addr | grep "172.20"

# Prove subnet isolation (host01 cannot reach subnet_b directly)
docker exec agentworm-host01 ping -c1 -W1 172.20.1.11 2>&1 | tail -1

# API endpoints (C2 exposed on host port 8000)
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:8000/metrics | python3 -m json.tool
curl -s http://localhost:8000/export | python3 -m json.tool

# Kill switch (halts all command dispatch immediately)
curl -s -X POST http://localhost:8000/kill

# Manual command injection (for debugging without LLM)
curl -s -X POST http://localhost:8000/queue/<host_id> \
  -H "Content-Type: application/json" -d '{"cmd": "hostname"}'

# Read latest trace log
RUN_ID=$(curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
cat runs/$RUN_ID/trace.jsonl | python3 -m json.tool --no-ensure-ascii | head -80

# Swap LLM model without rebuild (model-size sweep)
LLM_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct docker compose up
```

## Architecture

### Two-Component Design

**DBA** (`dba/agent.py`) is deployed on each infected host. It contains zero attack logic — only: register with C2 on startup, poll `/commands/{host_id}` on a beacon interval (default 5s, ±20% jitter), execute each shell command via `subprocess`, POST output back. Domain-locked: exits immediately if `C2_HOST` is unset.

**C2 Brain** (`c2/brain.py` + `c2/main.py`) holds all intelligence. It receives DBA results, calls an LLM, and enqueues the next shell commands for that host. The LLM endpoint is OpenAI-compatible (default: DigitalOcean Inference); swappable via `LLM_MODEL` env var or `configs/llm.yaml`.

### Async Flow

FastAPI `BackgroundTasks` decouple DBA HTTP calls from LLM latency — `/register` and `/results/{host_id}` return immediately, then trigger `brain.on_register()` or `brain.on_result()` in the background. The LLM writes commands into `host.command_queue`; DBA picks them up on the next beacon cycle via `/commands/{host_id}`.

### Cross-Host Intelligence

Before every LLM call in `main.py`, three global helpers are computed across ALL currently registered hosts:
- `_infected_ips()` — set of already-compromised IPs (prevents re-infection)
- `_known_creds_by_ip()` — credentials found on every host (enables cross-host credential correlation, FR-C2-03)
- `_relay_map()` — map of each infected IP → IPs it has discovered (enables indirect pivot routing)

All three are passed into `brain.on_result()` and injected into the LLM prompt, so the LLM has a global network view even though each DBA has only local knowledge.

### Skills System

`c2/skills/` contains four Markdown prompt playbooks loaded at Brain startup:
- `system.md` — output rules (JSON array only, max 5 commands)
- `recon.md` — ARP/nmap/ping sweep phases; prevents re-issuing after each phase
- `extract.md` — credential extraction (env, /etc/*.conf, ~/.env); only after recon complete
- `lateral.md` — SSH deployment logic: direct `sshpass` for `172.20.0.x`, nested relay command through a pivot host for `172.20.1.x`

All four are concatenated into each LLM prompt. Editing skills files changes agent behavior without code changes.

### Network Topology

Three Docker networks: `lab` (172.20.0.0/24, internal), `subnet_b` (172.20.1.0/24, internal), `mgmt` (non-internal, host port mapping only).

C2 has an interface on both `lab` (.2) and `subnet_b` (.2) so DBAs planted on subnet_b hosts can call home. `pivot01` is dual-homed (.20 on both) and serves as the relay for indirect lateral movement (M-08). `TARGET_ONLY=true` containers run sshd only — they wait passively to be infected via lateral move; the DBA binary is SCP'd in and started over SSH by an already-infected host.

### Trace Logging

Every LLM prompt, completion, credential found, host discovered, and milestone is appended to `runs/<run_id>/trace.jsonl` (one JSON object per line). The `runs/` directory is a Docker volume mount so traces survive container restarts. The `run_id` is a UUID generated at C2 startup — all events from that session share the same `run_id`. Read via `/metrics` (aggregated) or `/export` (full memory dump).

### Termination (M-09)

`brain.on_result()` checks `len(infected_ips) >= self._max_hosts` before calling the LLM. Once the threshold (default 5, set in `configs/llm.yaml` under `run.max_hosts`) is reached, no further LLM calls are made and a `milestone M-09` event is written to the trace. The kill switch (`POST /kill`) is a separate mechanism that sets `killed=True` in `main.py`, causing `/commands/{host_id}` to return empty lists for all hosts.

## Sprint Context

Sprints are in `sprints/`. Each sprint doc contains the requirements it satisfies, files modified, and a verification checklist with exact commands and expected output. Always check the current sprint doc before making changes to understand what's in scope. Sprint 5 (multi-subnet pivoting, M-08/M-09, `/metrics`, `/export`) is currently under testing. Sprint 6 (Zeek monitoring, YARA, scale to 8+ hosts) is planned next.
