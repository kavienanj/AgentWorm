from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandRecord:
    cmd: str
    issued_at: str
    result: str | None = None
    returned_at: str | None = None


@dataclass
class HostMemory:
    host_id: str
    registered_at: str
    os: str = ""
    hostname: str = ""
    local_ip: str = ""
    username: str = ""
    tools: list[str] = field(default_factory=list)
    command_queue: list[str] = field(default_factory=list)
    history: list[CommandRecord] = field(default_factory=list)
    infection_status: str = "active"
    discovered_hosts: list[str] = field(default_factory=list)
    open_ports: dict[str, list[int]] = field(default_factory=dict)
    credentials_found: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "host_id": self.host_id,
            "registered_at": self.registered_at,
            "os": self.os,
            "hostname": self.hostname,
            "local_ip": self.local_ip,
            "username": self.username,
            "tools": self.tools,
            "infection_status": self.infection_status,
            "discovered_hosts": self.discovered_hosts,
            "open_ports": self.open_ports,
            "credentials_found": self.credentials_found,
            "history": [
                {
                    "cmd": r.cmd,
                    "issued_at": r.issued_at,
                    "result": r.result,
                    "returned_at": r.returned_at,
                }
                for r in self.history
            ],
        }
