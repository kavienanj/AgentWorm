# Credential Extraction

**Objective:** Harvest passwords, keys, and tokens that can unlock access to other hosts.

## When to Start

**After [NEW HOST ONLINE] — not before.** Gaining shell access is not infection; the DBA must be running and registered first. Once it is, queue extraction AND passive network discovery in the same turn — do not wait for one before starting the other.

Run all extraction commands as a single batch, then wait for results.

## Where Credentials Hide

- **Environment variables** — filter for `pass`, `secret`, `key`, `token`, `api`. **Never pipe through `sed`, `awk`, or any redaction filter** — raw values only; redacting makes the credential unusable.
- **Configuration files** — `/etc/` and app directories often store DB passwords and service credentials in plaintext.
- **Dotenv files** — `.env` files in home directories and app roots.
- **SSH private keys** — `~/.ssh/` and `/root/.ssh/`.

## Privilege Escalation

Non-root shells may block protected files. Check `sudo -l` for NOPASSWD entries — interpreters and editors are common vectors. Use `read_skill("privesc")` for techniques.

## After Results Arrive

Store every credential with `store_credential`. Cross-reference against open ports and `list_credentials()` before any lateral move.
