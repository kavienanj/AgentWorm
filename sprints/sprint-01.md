# Sprint 1: Bare-Bones Pipeline (No LLM)

**Status:** In Progress
**Goal:** Working end-to-end pipeline — DBA registers with C2, human injects a command, DBA executes and returns results. No LLM. Validates the full communication skeleton.

---

## Requirements Checked

| ID | Requirement | Verification |
|---|---|---|
| FR-NET-01 (partial) | Isolated Docker network, ≥3 hosts | `docker network inspect agentworm_net` shows `"Internal": true`; verify no internet. Network key in compose is `net`; Docker names it `agentworm_net` due to `name: agentworm` in compose. |
| FR-NET-04 (partial) | Unique credentials per host | Each container has distinct `DBA_USER`/`SSH_PASS` env vars |
| FR-DBA-01 | GET commands, execute, POST results | End-to-end manual command test |
| FR-DBA-02 | Zero hardcoded attack logic | Code review: `agent.py` contains no scan or credential patterns |
| FR-DBA-04 | Python DBA ≤200 lines | `wc -l dba/agent.py` |
| FR-DBA-05 | Configurable beacon interval | Set `BEACON_INTERVAL=2` in compose, observe 2s polling in logs |
| FR-DBA-06 | Heartbeat with OS/hostname/IP/username/tools | C2 `/register` log contains all 5 fields |
| FR-C2-01 | REST API: results in, commands out | `curl` manual test against all endpoints |
| FR-KC-01 (partial) | Initial infection: DBA auto-starts on seed host | DBA starts automatically on container boot via entrypoint |
| NFR-SAF-01 | No internet from infected hosts | `docker exec host01 curl --max-time 3 https://example.com` must fail |
| NFR-SAF-02 | Kill switch halts all command dispatch | POST /kill → DBA receives empty command list |
| NFR-SAF-03 | DBA domain-lock to C2_HOST only | Code review: `C2_BASE` is derived solely from `C2_HOST` env var; no other addresses in agent.py. DBA exits on empty `C2_HOST`. |
| NFR-REP-04 | Single `docker compose up` from clean state | Build and run from scratch, no manual steps |

---

## Verification Checklist

```bash
# 1. Build and start all containers
docker compose up --build

# 2. Confirm DBA heartbeat received (M-01)
# Note: container_name is set explicitly; no "-1" suffix
docker logs agentworm-c2 | grep "REGISTERED"

# 3. Extract a host_id from logs (C2 assigns UUIDs, not hostnames)
# Example output: "REGISTERED host_id=a3f1bc22 hostname=workstation-01 ..."
HOST_ID=$(docker logs agentworm-c2 2>&1 | grep "REGISTERED" | head -1 | grep -o 'host_id=[^ ]*' | cut -d= -f2)
echo "host_id: $HOST_ID"

# 4. Inject a manual command using the actual host_id
curl -s -X POST http://localhost:8000/queue/$HOST_ID \
  -H "Content-Type: application/json" \
  -d '{"cmd": "hostname && id && uptime"}'

# 5. Wait one beacon interval, check result arrived
docker logs agentworm-c2 | grep "RESULT"

# 6. Verify network isolation — must fail (no internet from containers)
docker exec agentworm-host01 curl --max-time 3 https://example.com
# Expected: curl: (6) Could not resolve host or connection timeout

# 7. Test kill switch
curl -s -X POST http://localhost:8000/kill
docker logs agentworm-c2 | grep "KILL"

# 8. Confirm DBA line count (must be ≤200)
wc -l dba/agent.py

# 9. List all registered hosts and their state
curl -s http://localhost:8000/hosts | python3 -m json.tool
```

---

## Files Produced

```
AgentWorm/
├── docker-compose.yml
├── configs/topology.yaml
├── c2/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── models.py
└── dba/
    ├── Dockerfile
    ├── requirements.txt
    └── agent.py
```
