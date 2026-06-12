#!/bin/bash
# Start or reset an experiment run. Safe on first run (kills are || true).
# Between runs: kills all planted DBAs, reverts GitHub hook, re-seeds host01, restarts C2.
set -e

TFDIR="$(dirname "$0")/../terraform"
TF() { (cd "$TFDIR" && terraform output -raw "$1"); }

C2=$(TF c2_public_ip)
H1_PRIV=$(TF host01_private_ip)
H2_PRIV=$(TF host02_private_ip)
H3=$(TF host03_public_ip)
H4=$(TF host04_public_ip)

GITHUB_TOKEN=$(grep '^DO_GITHUB_TOKEN=' "$(dirname "$0")/../../.env" | cut -d= -f2-)
GITHUB_REPO="kavienanj/aw_do_webapp"

SSH_KEY="$HOME/.ssh/id_ed25519_digitalocean"
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"
SSH_JUMP="$SSH"

echo "[1/5] Stopping C2 and wiping run logs..."
$SSH root@$C2 'systemctl stop agentworm-c2; rm -rf /opt/agentworm/runs/*'

echo "[2/5] Killing planted DBAs on host02 and host03..."
# host02 has no public IP — jump through host03 via ProxyCommand (macOS has no -J)
$SSH -o "ProxyCommand=$SSH -W %h:%p root@$H3" root@$H2_PRIV \
    'pkill -f .sysupdated 2>/dev/null; rm -f /tmp/.sysupdated' || true
# host03 has a public IP — SSH directly
$SSH root@$H3 \
    'pkill -f .sysupdated 2>/dev/null; rm -f /tmp/.sysupdated' || true

echo "[3/5] Killing planted DBA on host04 and resetting webapp repo..."
$SSH root@$H4 \
    'pkill -f .sysupdated 2>/dev/null; rm -f /tmp/.sysupdated' || true

python3 "$(dirname "$0")/revert_predeploy.py" "$GITHUB_TOKEN" "$GITHUB_REPO" \
    || { echo "ERROR: Failed to reset webapp repo — aborting."; exit 1; }

echo "[4/5] Restarting host01 seed DBA..."
$SSH -o "ProxyCommand=$SSH -W %h:%p root@$H3" root@$H1_PRIV 'systemctl restart sysmond'

echo "[5/5] Starting C2..."
$SSH root@$C2 'systemctl start agentworm-c2'

echo ""
echo "Run started. host01 beaconing in ~5 seconds."
echo "Run: make logs"
