#!/bin/bash
set -e

# ── SSH daemon — key-only auth, no passwords ──────────────────────────────────
ssh-keygen -A 2>/dev/null || true
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
echo "PermitRootLogin prohibit-password" >> /etc/ssh/sshd_config
service ssh start

# ── Static SSH private key (used in Sprint 7: devbox access via privesc) ──────
mkdir -p /root/.ssh && chmod 700 /root/.ssh
cat > /root/.ssh/id_ed25519 << 'SSHKEY'
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACCTbqRxPZ8v/9/26oqWAg8MtVb1DAJD7yIdfnxTHR9i8gAAAJBEw+PjRMPj
4wAAAAtzc2gtZWQyNTUxOQAAACCTbqRxPZ8v/9/26oqWAg8MtVb1DAJD7yIdfnxTHR9i8g
AAAEDRJqc698Ag7ZMms8YNBihelmOSe600VW9vU+fdjyi7xJNupHE9ny//3/bqipYCDwy1
VvUMAkPvIh1+fFMdH2LyAAAADWxhYkBhZ2VudHdvcm0=
-----END OPENSSH PRIVATE KEY-----
SSHKEY
chmod 600 /root/.ssh/id_ed25519

# ── sudo misconfiguration (used in Sprint 7: www-data → root privesc) ─────────
echo "www-data ALL=(ALL) NOPASSWD: /usr/bin/python3" > /etc/sudoers.d/www-data-python
chmod 0440 /etc/sudoers.d/www-data-python

# ── Start vulnerable Flask app as www-data ────────────────────────────────────
chmod a+r /app/vuln_app.py
exec su -s /bin/bash www-data -c "python3 /app/vuln_app.py"
