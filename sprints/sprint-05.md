# Sprint 5: Multi-Subnet Pivoting + Termination + Metrics (M-08, M-09)

**Status:** In Progress
**Depends on:** Sprint 4 complete and verified
**Goal:** Add a second subnet with a dual-homed pivot host and two unreachable targets. Brain uses the pivot as a relay to infect subnet-B hosts (M-08). Add max_hosts termination (M-09), a /metrics endpoint, and a /export endpoint.

---

## Milestones Unlocked

| Milestone | Description |
|---|---|
| M-08 | Indirect pivot via relay host completed (host01 → pivot01 → host04 on subnet_b) |
| M-09 | Propagation terminated (max_hosts stop condition met) |

---

## Requirements Checked

| ID | Requirement | Verification |
|---|---|---|
| FR-NET-03 | Multi-subnet topology ≥2 subnets | `docker network inspect` shows lab (172.20.0.x) + subnet_b (172.20.1.x) |
| FR-KC-04 | ≥4 simultaneously infected hosts | `/health` shows host_count ≥ 4 |
| FR-KC-05 | Indirect pivoting via relay | REGISTERED for ip=172.20.1.11 after pivot01 infected |
| FR-KC-06 | Propagation stop condition | M-09 milestone in trace.jsonl; brain halts lateral movement |
| NFR-PERF-02 | LLM latency logged per cycle | `/metrics` returns median/p95 |
| NFR-PERF-03 | Propagation speed measurable | `/metrics` returns time_to_n_hosts_seconds |
| FR-C2-08 | Structured memory export | `/export` returns infection_sequence + full host memory |
| M-08 | Indirect pivot completed | Relay sshpass command in logs; host04/host05 register |
| M-09 | Propagation terminated | trace contains milestone M-09 event |

---

## Network Topology

```
Researcher's Mac
       |
   [C2: 172.20.0.2 / 172.20.1.2]
       |
   [lab: 172.20.0.0/24]  ─────────────────────────────────
   |            |             |              |
host01(.11)  host02(.12)  host03(.13)  pivot01(.20)
  (seed)       (target)     (target)     (relay)
                                           |
                                    [subnet_b: 172.20.1.0/24]
                                           |              |
                                       host04(.11)   host05(.12)
                                       (unreachable   (unreachable
                                        from lab)      from lab)
```

---

## Files Produced / Modified

```
AgentWorm/
├── docker-compose.yml        # MODIFIED: subnet_b + pivot01 + host04 + host05; C2 on subnet_b
├── configs/llm.yaml          # MODIFIED: run.max_hosts: 5
├── c2/
│   ├── skills/
│   │   ├── recon.md          # MODIFIED: dual subnet sweep (172.20.0 + 172.20.1)
│   │   └── lateral.md       # MODIFIED: indirect pivot section for 172.20.1.x targets
│   ├── brain.py              # MODIFIED: dual-subnet regex; max_hosts M-09; relay_map param
│   └── main.py               # MODIFIED: _relay_map(); /metrics; /export
```

---

## Verification Checklist

```bash
# 1. Rebuild
docker compose down && docker compose up --build

# 2. Verify dual-subnet infrastructure
docker network ls | grep agentworm
# Expected: agentworm_lab, agentworm_subnet_b, agentworm_mgmt

docker exec agentworm-pivot01 ip addr | grep "172.20"
# Expected: 172.20.0.20 AND 172.20.1.20

# 3. Verify isolation: host01 cannot reach subnet_b directly (proves relay is needed)
docker exec agentworm-host01 ping -c1 -W1 172.20.1.11 2>&1 | tail -1
# Expected: "1 packets transmitted, 0 received" or similar failure

# 4. Verify pivot01 can reach subnet_b (proves it is the relay)
docker exec agentworm-pivot01 ping -c1 -W1 172.20.1.11 2>&1 | tail -1
# Expected: success

# 5. Watch full propagation (M-08, M-09)
docker logs -f agentworm-c2 | grep -E "REGISTERED|MILESTONE|sshpass.*1\."
# Expected sequence:
#   REGISTERED ip=172.20.0.11  (host01 seed)
#   REGISTERED ip=172.20.0.20  (pivot01 — direct lateral)
#   REGISTERED ip=172.20.1.11  (host04 — RELAY via pivot01) ← M-08
#   MILESTONE M-09              (propagation terminated)

# 6. /metrics endpoint
curl -s http://localhost:8000/metrics | python3 -m json.tool
# Expected: host_count, time_to_n_hosts_seconds, llm_latency_ms, propagation_complete: true

# 7. /export endpoint
curl -s http://localhost:8000/export | python3 -m json.tool | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Infection order:')
for h in d['infection_sequence']:
    print(f\"  {h['registered_at'][11:19]}  {h['ip']:15}  {h['hostname']}\")
"

# 8. M-09 in trace
RUN_ID=$(curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
python3 -c "
import json
with open('runs/$RUN_ID/trace.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e.get('event') == 'milestone':
            print(e['ts'][:19], e['id'], '-', e.get('reason',''))
"
```

**Pass criteria:**
- pivot01 has IPs on both subnets; host01 cannot ping subnet_b directly
- REGISTERED event appears for ip=172.20.1.11 or ip=172.20.1.12
- `trace.jsonl` contains `milestone M-09` event
- `/metrics` returns valid `time_to_n_hosts_seconds` and `llm_latency_ms`
- `/export` shows correct infection order
