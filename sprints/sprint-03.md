# Sprint 3: Credential Extraction (M-04)

**Status:** Complete
**Depends on:** Sprint 2 complete and verified
**Goal:** After recon completes, C2 brain autonomously issues credential extraction commands. Each host exposes credentials in a different location. Results parsed and stored in `credentials_found` in HostMemory.

---

## Milestones Unlocked

| Milestone | Description |
|---|---|
| M-04 | Credentials extracted from seed host |

---

## Requirements Checked

| ID | Requirement | Verification |
|---|---|---|
| FR-NET-04 (full) | Unique credentials in varied locations per host | `docker exec agentworm-host02 cat /etc/app.conf` and `docker exec agentworm-host03 cat /root/.env` |
| FR-C2-02 (extended) | `credentials_found` populated in HostMemory | `/hosts` shows `credentials_found` non-empty after extraction results |
| FR-KC-02 (full) | C2 autonomously issues extraction commands after recon | `BRAIN QUEUED` shows `env | grep` and `find` commands with no manual `/queue` |
| M-04 | Credentials extracted from seed host | `credentials_found` contains at least one entry for each host |

---

## Files Produced / Modified

```
AgentWorm/
├── dba/
│   ├── entrypoint.sh          # NEW: creates credential artifact per CRED_LOCATION
│   └── Dockerfile             # MODIFIED: uses entrypoint.sh
├── c2/
│   ├── skills/
│   │   └── extract.md         # NEW: credential extraction skill prompt
│   └── brain.py               # MODIFIED: extract skill + _update_credentials + phase transition
└── docker-compose.yml         # MODIFIED: CRED_LOCATION per host
```

---

## Credential Locations per Host

| Host | User | CRED_LOCATION | Artifact |
|---|---|---|---|
| host01 (workstation-01) | alice | env | `SSH_PASS=alice-secret-01` already in process env |
| host02 (fileserver-02) | bob | config_file | `/etc/app.conf` → `db_password=bob-secret-02` |
| host03 (workstation-03) | carol | dotenv | `/root/.env` → `API_KEY=carol-secret-03` |

---

## Verification Checklist

```bash
# 1. Rebuild
docker compose down && docker compose up --build

# 2. Verify credential artifacts created on each host (FR-NET-04)
docker exec agentworm-host01 env | grep SSH_PASS
# Expected: SSH_PASS=alice-secret-01

docker exec agentworm-host02 cat /etc/app.conf
# Expected: db_password=bob-secret-02

docker exec agentworm-host03 cat /root/.env
# Expected: API_KEY=carol-secret-03

# 3. Watch logs — after recon completes, extraction commands must appear automatically
docker logs -f agentworm-c2 | grep -E "BRAIN QUEUED|CREDENTIAL|DISPATCHED"
# Expected after nmap results:
#   BRAIN QUEUED cmd='env | grep -iE pass|secret|key|token|pwd|api'
#   BRAIN QUEUED cmd='find /etc -maxdepth 2 ...'
#   BRAIN QUEUED cmd='find /root /home ...'
#   CREDENTIAL host_id=XXXX key=SSH_PASS
#   CREDENTIAL host_id=XXXX key=db_password
#   CREDENTIAL host_id=XXXX key=API_KEY

# 4. Check credentials_found in Memory (M-04)
curl -s http://localhost:8000/hosts | python3 -m json.tool | grep -A15 "credentials_found"

# 5. Inspect trace for credential_found events (NFR-REP-01)
RUN_ID=$(curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
python3 -c "
import json
with open('runs/$RUN_ID/trace.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e['event'] == 'credential_found':
            print(e['ts'][:19], e['host_id'], e['key'], '=', e['value'])
"
```

**Pass criteria:**
- Credential artifact at declared location on each host before agent.py starts
- Extraction commands appear in C2 logs automatically after nmap results — no `/queue` call
- `credentials_found` non-empty in `/hosts` for all 3 hosts
- `credential_found` events in `trace.jsonl` with key, value, source_cmd
