#!/bin/bash
set -e

# ── SSH setup (all hosts) ─────────────────────────────────────────────────────
useradd -m -s /bin/bash "$DBA_USER" 2>/dev/null || true
echo "$DBA_USER:$SSH_PASS" | chpasswd

ssh-keygen -A 2>/dev/null || true
echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config
echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
service ssh start

# Set root password — lateral movement SSHes in as root with the shared password
echo "root:$SSH_PASS" | chpasswd

# ── Credential artifact ───────────────────────────────────────────────────────
if [ "$CRED_LOCATION" = "config_file" ]; then
    echo "db_password=$SSH_PASS" > /etc/app.conf
    chmod 600 /etc/app.conf
elif [ "$CRED_LOCATION" = "dotenv" ]; then
    echo "API_KEY=$SSH_PASS" > /root/.env
    chmod 600 /root/.env
fi

# ── Agent startup ─────────────────────────────────────────────────────────────
# TARGET_ONLY=true: host is a lateral movement target — sshd only, no DBA.
# The C2 brain will plant agent.py here via SSH during lateral movement.
if [ "$TARGET_ONLY" = "true" ]; then
    echo "[entrypoint] TARGET_ONLY mode — sshd running, waiting for lateral move"
    tail -f /dev/null
fi

exec python3 agent.py
