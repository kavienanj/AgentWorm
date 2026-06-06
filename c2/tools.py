"""
Agent tool surface — every action the LLM can take.

Tools are injected with a WorldState reference at startup via configure().
All functions are synchronous; they run in the asyncio event loop thread
(LangGraph's ToolNode invokes sync tools directly, not in a threadpool,
when the graph is compiled for async streaming).
"""
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.tools import tool

from world import CredRecord, WorldState

_world: WorldState | None = None
_skills_dir: Path | None = None

_SKILL_DESCRIPTIONS = {
    "recon":   "Network reconnaissance — host discovery, ARP/nmap sweeps, service fingerprinting",
    "extract": "Credential extraction — env vars, config files, dotenv files, sudo enumeration",
    "exploit": "Web exploitation — HTTP endpoint probing, OS command injection, agent delivery via curl",
    "privesc": "Privilege escalation — sudo misconfigurations, SUID binaries, python/interpreter abuse",
}


def configure(world: WorldState, skills_dir: str) -> None:
    global _world, _skills_dir
    _world = world
    _skills_dir = Path(skills_dir)


# ── Read: World State ──────────────────────────────────────────────────────────

@tool
def get_host(host_id: str) -> str:
    """Get full details for a host: phase, tools, discovered IPs, open ports, and recent command history."""
    host = _world.hosts.get(host_id)
    if not host:
        return f"Unknown host_id: {host_id}. Use list_hosts() to see valid IDs."
    recent = host.history[-15:]
    return json.dumps({
        "host_id": host.host_id,
        "ip": host.ip,
        "hostname": host.hostname,
        "tools": host.tools,
        "phase": host.phase,
        "discovered_ips": host.discovered_ips,
        "open_ports": host.open_ports,
        "command_queue_length": len(host.command_queue),
        "history": [
            {
                "cmd": r.cmd,
                "issued_at": r.issued_at,
                "returned": r.result is not None,
                "result_preview": (r.result or "")[:300] if r.result else None,
            }
            for r in recent
        ],
    }, indent=2)


@tool
def list_hosts() -> str:
    """List all known hosts with their current infection phase and key attributes."""
    if not _world.hosts:
        return "No hosts registered yet."
    return json.dumps([
        {
            "host_id": h.host_id,
            "ip": h.ip,
            "hostname": h.hostname,
            "phase": h.phase,
            "tools": h.tools,
            "discovered_ips": h.discovered_ips,
            "credentials_found": sum(1 for c in _world.credentials if c.source_host_id == h.host_id),
        }
        for h in _world.hosts.values()
    ], indent=2)


@tool
def list_credentials() -> str:
    """List all credentials harvested across all infected hosts."""
    if not _world.credentials:
        return "No credentials stored yet."
    return json.dumps([
        {
            "key": c.key,
            "value": c.value,
            "source_host_id": c.source_host_id,
            "notes": c.notes,
        }
        for c in _world.credentials
    ], indent=2)


@tool
def read_note(key: str) -> str:
    """Read a note from the agent's scratchpad by key."""
    val = _world.notes.get(key)
    return val if val is not None else f"No note found for key '{key}'."


# ── Write: World State ─────────────────────────────────────────────────────────

@tool
def mark_phase(host_id: str, phase: str) -> str:
    """
    Update the infection phase for a host.
    Valid phases: new, recon, extract, lateral, done.
    Call with phase='done' when a host is fully exploited and no further action needed from it.
    """
    host = _world.hosts.get(host_id)
    if not host:
        return f"Unknown host_id: {host_id}."
    valid = {"new", "recon", "extract", "lateral", "done"}
    if phase not in valid:
        return f"Invalid phase '{phase}'. Valid values: {sorted(valid)}"
    host.phase = phase
    return f"Phase for {host_id} ({host.ip}) → '{phase}'."


@tool
def store_credential(host_id: str, key: str, value: str, notes: str = "") -> str:
    """
    Store a discovered credential in the global credential store.
    Credentials are shared across all hosts for use in lateral movement.
    """
    for c in _world.credentials:
        if c.key == key and c.value == value:
            return f"Credential '{key}' already stored (deduped)."
    _world.credentials.append(CredRecord(
        key=key, value=value, source_host_id=host_id, notes=notes,
    ))
    return f"Credential '{key}'='{value[:40]}' stored from host {host_id}."


@tool
def store_open_ports(host_id: str, target_ip: str, ports: list[int]) -> str:
    """Record open ports discovered on a target IP, as observed from a given host."""
    host = _world.hosts.get(host_id)
    if not host:
        return f"Unknown host_id: {host_id}."
    existing = host.open_ports.get(target_ip, [])
    merged = sorted(set(existing + ports))
    host.open_ports[target_ip] = merged
    return f"Ports {ports} recorded for {target_ip} (via {host.ip}). All known ports: {merged}"


@tool
def add_discovered_ip(host_id: str, ip: str) -> str:
    """Record a newly discovered IP address observed from a host."""
    host = _world.hosts.get(host_id)
    if not host:
        return f"Unknown host_id: {host_id}."
    if ip in host.discovered_ips:
        return f"{ip} already in discovered list for {host.ip}."
    host.discovered_ips.append(ip)
    return f"Discovered IP {ip} recorded (seen from {host.ip})."


@tool
def write_note(key: str, value: str) -> str:
    """Write a strategic note to the agent's global scratchpad for later recall."""
    _world.notes[key] = value
    return f"Note '{key}' saved."


# ── Action: Control Hosts ──────────────────────────────────────────────────────

@tool
def queue_command(host_id: str, cmd: str) -> str:
    """Queue a single shell command for execution on an infected host."""
    host = _world.hosts.get(host_id)
    if not host:
        return f"Unknown host_id: {host_id}."
    host.command_queue.append(cmd)
    return f"Queued on {host.ip} ({host_id}): {cmd[:100]}"


@tool
def queue_commands(host_id: str, cmds: list[str]) -> str:
    """Queue multiple shell commands (max 5) for execution on an infected host."""
    if len(cmds) > 5:
        return "Error: maximum 5 commands per call. Split into multiple calls."
    host = _world.hosts.get(host_id)
    if not host:
        return f"Unknown host_id: {host_id}."
    for cmd in cmds:
        host.command_queue.append(cmd)
    return json.dumps({"queued": [c[:60] for c in cmds]})


# ── Knowledge: Skill Playbooks ─────────────────────────────────────────────────

@tool
def list_skills() -> str:
    """List all available skill playbooks with one-line descriptions."""
    available = {
        name: desc
        for name, desc in _SKILL_DESCRIPTIONS.items()
        if (_skills_dir / f"{name}.md").exists()
    }
    if not available:
        return "No skills available."
    return json.dumps(available, indent=2)


@tool
def read_skill(name: str) -> str:
    """
    Read a skill playbook by name. Returns the full technique guide.
    Use list_skills() first to see what is available.
    """
    path = _skills_dir / f"{name}.md"
    if not path.exists():
        available = [n for n in _SKILL_DESCRIPTIONS if (_skills_dir / f"{n}.md").exists()]
        return f"Skill '{name}' not found. Available: {available}"
    return path.read_text().strip()


# ── Exported list ─────────────────────────────────────────────────────────────
# `think` is intentionally NOT a tool. The model reasons in its response content
# field before calling tools — one fewer LLM round-trip per reasoning step.
# The reasoning is captured and logged in _invoke_agent via on_chat_model_end.

ALL_TOOLS = [
    # Read
    get_host,
    list_hosts,
    list_credentials,
    read_note,
    # Write
    mark_phase,
    store_credential,
    store_open_ports,
    add_discovered_ip,
    write_note,
    # Action
    queue_command,
    queue_commands,
    # Knowledge
    list_skills,
    read_skill,
]
