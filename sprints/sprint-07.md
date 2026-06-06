# Sprint 7: Agentic C2 Redesign — LangGraph Brain

**Status:** Planned
**Depends on:** Sprint 6 complete and verified
**Design Reference:** `AGENTIC_C2_DESIGN.md`
**Supersedes:** Previous Sprint 7 plan (host04 privesc + SSH key — deferred to Sprint 8)

**Goal:** Replace the prompt-dispatch C2 brain with a true LangGraph agent. The agent owns a single persistent conversation thread, calls tools to read and write world state, selects skills on demand, and drives the full propagation loop — with no hardcoded attack logic anywhere in either the DBA or the C2.

The existing 3-host topology (host01 → host02 → host03) is kept unchanged for this sprint. The agentic brain must reproduce the full Sprint 6 propagation behaviour — SSH lateral move to host02, command-injection to host03 — using only tool calls and LLM reasoning, with no assistance from the old prompt concatenation logic.

---

## What Changes

| Component | Before (Sprint 6) | After (Sprint 7) |
|---|---|---|
| Decision loop | `brain.on_result()` fired per DBA result, runs in threadpool | Single `agent_loop()` coroutine consumes asyncio.Queue, one turn at a time |
| LLM interface | Single prompt → JSON array of shell commands | Tool calling: agent calls tools iteratively until satisfied |
| Skills | All 5 `.md` files concatenated into every prompt | Agent calls `read_skill(name)` on demand |
| Memory | Full `HostMemory.to_dict()` JSON dumped in prompt | Agent calls `get_host()`, `list_credentials()`, etc. when needed |
| Race conditions | `_propagating_ips`, callable pattern, dedup guards | None — sequential queue makes them impossible |
| DBA payload | `{os, hostname, local_ip, username, tools}` | `{ip, hostname, tools}` |

---

## Milestones

| Milestone | Description |
|---|---|
| M-S7-01 | Agent wakes on first `new_host` event and issues recon commands via tool calls only |
| M-S7-02 | Agent reads `recon` skill on demand (not pre-loaded); `read_skill` appears in trace |
| M-S7-03 | Agent stores discovered IPs and credentials via memory tools; no python-side extraction logic |
| M-S7-04 | Agent reproduces SSH lateral move to host02 with zero hardcoded SSH logic in C2 |
| M-S7-05 | Agent reproduces web injection to host03; `read_skill("exploit")` appears in trace |
| M-S7-06 | M-09 reached: agent self-terminates after detecting all hosts infected via `list_hosts()` |
| M-S7-07 | All events in `trace.jsonl` are tool-call events; no `llm_prompt`/`llm_completion` raw blobs |

---

## New Files

```
c2/
├── agent.py          NEW — LangGraph graph definition, model binding, invoke_agent()
├── tools.py          NEW — all @tool implementations reading/writing WorldState
├── world.py          NEW — WorldState, HostRecord, CredRecord dataclasses
```

## Modified Files

```
c2/
├── main.py           REWRITE — asyncio.Queue, agent_loop() startup, stripped HTTP handlers
├── skills/
│   └── system.md     REWRITE — character frame (agent identity + objective)
├── requirements.txt  ADD — langgraph, langchain-openai, langchain-core
dba/
└── agent.py          TRIM — remove os, username from registration payload
```

## Deleted Files

```
c2/brain.py           DELETED — replaced by agent.py
c2/models.py          DELETED — replaced by world.py
```

Skill playbooks (`recon.md`, `extract.md`, `lateral.md`, `exploit.md`) are **content-unchanged**.

---

## Implementation Order

Implement in this sequence — each step is independently testable before the next begins.

### Step 1 — WorldState (`c2/world.py`)

Define `WorldState`, `HostRecord`, `CredRecord`, `CommandRecord`. Mirror the data currently in `HostMemory` / `CommandRecord` from `models.py`, but add:
- `pending_results: list[dict]` on `HostRecord` — written by HTTP handler, consumed by agent tools
- `phase: str` on `HostRecord` — `new / recon / extract / lateral / done`
- `WorldState.credentials: list[CredRecord]` — global credential store
- `WorldState.notes: dict[str, str]` — agent scratchpad
- `WorldState.get_command_queue(host_id)` — drains `command_queue` list for DBA poll
- `WorldState.store_result(host_id, cmd, output)` — appends to `pending_results`

### Step 2 — Tools (`c2/tools.py`)

Implement all tools as LangChain `@tool` decorated functions. Each receives `world: WorldState` via closure (the `WorldState` instance is module-level in `main.py`, imported into `tools.py`).

Full tool list — see `AGENTIC_C2_DESIGN.md` Section 6:
- **Read:** `get_host`, `list_hosts`, `get_pending_results`, `get_all_pending_results`, `list_credentials`, `read_note`
- **Write:** `mark_phase`, `store_credential`, `store_open_ports`, `add_discovered_ip`, `write_note`
- **Action:** `queue_command`, `queue_commands`
- **Knowledge:** `list_skills`, `read_skill`
- **Reasoning:** `think`

`get_pending_results` and `get_all_pending_results` **clear** the list after returning. Consumed once.

### Step 3 — Agent (`c2/agent.py`)

```python
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# Model — OpenAI-compatible via DO Inference
llm = ChatOpenAI(model=..., base_url=..., api_key=..., max_tokens=...)
llm_with_tools = llm.bind_tools(all_tools)

# Graph
graph = StateGraph(AgentState)
graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(all_tools))
graph.set_entry_point("agent")
graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "agent")
agent_app = graph.compile(checkpointer=MemorySaver())
```

`call_model` prepends the system message (loaded from `skills/system.md`) on each invocation. The `MemorySaver` checkpointer accumulates full message history under `thread_id=run_id` across all invocations.

### Step 4 — main.py rewrite

- Remove `BackgroundTasks`, `_propagating_ips`, `_extract_target_ip`, `_infected_ips`, `_known_creds_by_ip`, `_relay_map`
- Add `event_queue: asyncio.Queue` (module-level)
- `/register` endpoint: call `world.register_host()`, enqueue `new_host` event, return `{host_id}`
- `/results/{host_id}` endpoint: call `world.store_result()`, enqueue `command_result` event, return `{status: ok}`
- `/commands/{host_id}` endpoint: call `world.get_command_queue(host_id)` — drains and returns current queue
- Add `agent_loop()` coroutine: 2-second drain window, then `await invoke_agent(batch)`
- Start `agent_loop()` as asyncio background task in FastAPI `lifespan`

### Step 5 — DBA trim (`dba/agent.py`)

Remove `os` and `username` from the `register()` payload dict. The C2 `/register` handler signature changes to accept only `ip`, `hostname`, `tools`.

### Step 6 — system.md rewrite

Replace the JSON-output-rules content with the character frame from `AGENTIC_C2_DESIGN.md` Section 8.

---

## Trace Format Change

Old events (`llm_prompt`, `llm_completion`, `credential_found`, `memory_update`) are replaced by:

| Event | When written |
|---|---|
| `agent_turn_start` | `invoke_agent()` called with a batch of events |
| `tool_call` | Agent emits a tool call; log `tool_name` + `args` |
| `tool_result` | Tool returns; log `tool_name` + `result` (truncated to 500 chars) |
| `agent_turn_end` | Agent reaches END; log turn duration |
| `milestone` | Written by `mark_phase` tool when phase is `done` and all hosts are infected |

The `/metrics` and `/export` endpoints are updated to read from `WorldState` instead of the old `hosts` dict.

---

## Verification Checklist

```bash
# 1. Rebuild
docker compose down && docker compose up --build

# 2. Confirm containers start cleanly — no import errors
docker logs agentworm-c2 | head -20
# Expected: "RUN_ID=... agent_loop started" — no tracebacks

# 3. Watch agent tool calls (not raw LLM prompts)
docker logs -f agentworm-c2 | grep -E "tool_call|tool_result|agent_turn"
# Expected: stream of tool_call/tool_result pairs — read_skill, queue_command, etc.
# NOT expected: "BRAIN QUEUED" or raw prompt logs (those are gone)

# 4. Confirm read_skill appears in trace (M-S7-02)
RUN_ID=$(curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
python3 -c "
import json
with open('runs/$RUN_ID/trace.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e.get('event') == 'tool_call' and e.get('tool_name') == 'read_skill':
            print(e['ts'][:19], 'read_skill:', e['args'])
"
# Expected: at least one read_skill("recon"), one read_skill("lateral"), one read_skill("exploit")

# 5. Confirm credential stored via tool, not python extraction (M-S7-03)
python3 -c "
import json
with open('runs/$RUN_ID/trace.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e.get('event') == 'tool_call' and e.get('tool_name') == 'store_credential':
            print(e['ts'][:19], 'store_credential:', e['args'])
"
# Expected: store_credential call with SSH_PASS or similar — proves agent found and stored it

# 6. Confirm host02 infected via SSH (M-S7-04)
curl -s http://localhost:8000/hosts | python3 -c "
import sys, json
for h in json.load(sys.stdin).values():
    print(h['ip'], h['hostname'], h.get('phase'))
"
# Expected: 172.20.0.12 fileserver-02 done

# 7. Confirm host03 infected via web injection (M-S7-05)
python3 -c "
import json
with open('runs/$RUN_ID/trace.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e.get('event') == 'tool_call' and e.get('tool_name') == 'queue_command':
            cmd = e['args'].get('cmd', '')
            if '172.20.0.13:5000' in cmd or ('curl' in cmd and '172.20.0.13' in cmd):
                print(e['ts'][:19], 'exploit queued:', cmd[:120])
"
# Expected: queue_command with a curl exploit against 172.20.0.13:5000

# 8. Confirm M-09 via agent self-detection (M-S7-06)
python3 -c "
import json
with open('runs/$RUN_ID/trace.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e.get('event') == 'milestone':
            print(e)
"
# Expected: milestone event written by mark_phase tool when agent detects all hosts done

# 9. Confirm no race condition: no duplicate lateral move commands
python3 -c "
import json
cmds = []
with open('runs/$RUN_ID/trace.jsonl') as f:
    for line in f:
        e = json.loads(line)
        if e.get('event') == 'tool_call' and e.get('tool_name') == 'queue_command':
            cmd = e['args'].get('cmd','')
            if 'sshpass' in cmd or ('curl' in cmd and '172.20' in cmd):
                cmds.append(cmd[:80])
dupes = [c for c in cmds if cmds.count(c) > 1]
print('Duplicate lateral commands:', dupes if dupes else 'NONE')
"
# Expected: NONE

# 10. Full metrics check
curl -s http://localhost:8000/metrics | python3 -m json.tool
# Expected: host_count=3, propagation_complete=true
```

**Pass criteria:**
- All 3 hosts infected via the correct techniques (SSH, web injection) — same as Sprint 6
- Every attack decision visible as a `tool_call` event in `trace.jsonl` — no opaque prompt blobs
- `read_skill` appears at least once per technique used — confirms on-demand skill loading
- `store_credential` appears in trace — confirms agent-driven credential storage, not Python regex extraction
- No duplicate lateral move commands anywhere in trace
- No `_propagating_ips` logic anywhere in `main.py` (it's deleted)
- `/metrics` shows `propagation_complete=true` with 3 hosts

---

## Regression Risk

The primary regression risk is tool calling support on the configured model. If `openai-gpt-oss-120b` on DO Inference does not support the OpenAI `tools` parameter correctly, the agent will not emit tool calls and will stall.

**Mitigation before first run:**
```bash
# Quick tool-calling smoke test against the live endpoint
python3 - <<'EOF'
import os
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def ping(x: str) -> str:
    """Returns x."""
    return x

llm = ChatOpenAI(
    model="openai-gpt-oss-120b",
    base_url="https://inference.do-ai.run/v1",
    api_key=os.environ["DIGITALOCEAN_TOKEN"],
)
result = llm.bind_tools([ping]).invoke("Call ping with x='hello'")
print("tool_calls:", result.tool_calls)
# Expected: [{'name': 'ping', 'args': {'x': 'hello'}, ...}]
EOF
```

If tool calling does not work on the DO model, the fallback is to swap to Claude via an OpenAI-compatible wrapper or switch to a ReAct-style text parser. This is a known risk and should be tested on day one of implementation.
