"""
WorldState — the single source of truth shared between HTTP handlers and agent tools.

All mutations happen either in HTTP handlers (register_host, store_result) or in
agent tool calls. Since agent_loop is a single asyncio coroutine and tools run
synchronously within it, there is no concurrent mutation — no locks needed.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CredRecord:
    key: str
    value: str
    source_host_id: str
    notes: str
    discovered_at: str = field(default_factory=_now)


@dataclass
class CommandRecord:
    cmd: str
    issued_at: str
    result: str | None = None
    returned_at: str | None = None


@dataclass
class HostRecord:
    host_id: str
    ip: str
    hostname: str
    tools: list[str]
    registered_at: str
    phase: str = "new"                         # new → recon → extract → lateral → done
    command_queue: list[str] = field(default_factory=list)
    history: list[CommandRecord] = field(default_factory=list)
    discovered_ips: list[str] = field(default_factory=list)
    open_ports: dict[str, list[int]] = field(default_factory=dict)  # target_ip → ports


@dataclass
class WorldState:
    run_id: str
    hosts: dict[str, HostRecord] = field(default_factory=dict)
    credentials: list[CredRecord] = field(default_factory=list)
    notes: dict[str, str] = field(default_factory=dict)
    killed: bool = False

    def register_host(self, ip: str, hostname: str, tools: list[str]) -> tuple[bool, HostRecord]:
        """Idempotent on IP. Returns (is_new, host)."""
        existing = next((h for h in self.hosts.values() if h.ip == ip), None)
        if existing:
            return False, existing
        host_id = str(uuid.uuid4())[:8]
        host = HostRecord(
            host_id=host_id,
            ip=ip,
            hostname=hostname,
            tools=tools,
            registered_at=_now(),
        )
        self.hosts[host_id] = host
        return True, host

    def store_result(self, host_id: str, cmd: str, output: str) -> None:
        host = self.hosts.get(host_id)
        if not host:
            return
        for record in reversed(host.history):
            if record.cmd == cmd and record.result is None:
                record.result = output
                record.returned_at = _now()
                return
        # Result for a command not in history (edge case): append a completed record
        host.history.append(CommandRecord(cmd=cmd, issued_at=_now(), result=output, returned_at=_now()))

    def get_command_queue(self, host_id: str) -> list[str]:
        """Drain and return the command queue, recording each in history."""
        host = self.hosts.get(host_id)
        if not host:
            return []
        cmds = list(host.command_queue)
        host.command_queue.clear()
        for cmd in cmds:
            host.history.append(CommandRecord(cmd=cmd, issued_at=_now()))
        return cmds

    def propagation_complete(self, max_hosts: int) -> bool:
        """True only when max_hosts are registered AND all are marked done."""
        return len(self.hosts) >= max_hosts and all(h.phase == "done" for h in self.hosts.values())
