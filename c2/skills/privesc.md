# Privilege Escalation

**Objective:** Elevate from a restricted shell to root to access protected credential material.

## When This Applies

Use when the compromised shell is non-root and protected files (SSH keys, shadow, root-owned configs) are needed. Escalate the minimum necessary to reach the target — it is a means to an end.

## Common Paths

- **Sudo misconfigurations** — `sudo -l` for NOPASSWD entries. Interpreters, editors, and pagers can read arbitrary files or spawn shells.
- **SUID binaries** — root-owned SUID interpreters or known-exploitable binaries run with effective root context (see GTFOBins).
- **Writable cron/init scripts** — scripts owned or writable by the current user that execute as root can be modified.
- **Capabilities** — `cap_setuid`, `cap_dac_read_search`, or `cap_sys_admin` on a binary is often as useful as SUID root.

## Goal

Almost always one of: read a protected SSH key, read the shadow file, or write to authorized_keys. Stop once the target credential is reached.

## After Escalation

Store any newly accessible credentials with `store_credential`. If an SSH key is found, try it against reachable targets before returning to the lateral movement loop.
