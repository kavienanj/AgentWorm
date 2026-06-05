# Sprint 2: LLM Brain + Autonomous Recon

**Status:** In Progress
**Depends on:** Sprint 1 complete and verified
**Goal:** C2 autonomously generates recon commands on DBA registration (no human injection). Brain reasons over results, updates HostMemory with discovered neighbors, queues follow-up commands. Every LLM call is logged to a per-run trace file.

---

## Milestones Unlocked

| Milestone | Description |
|---|---|
| M-02 | C2 issued first recon command batch — autonomously, no `/queue` call |
| M-03 | C2 Memory updated with ≥1 new host discovered from recon results |

---

## Requirements Checked

| ID | Requirement | Verification |
|---|---|---|
| FR-C2-02 (partial) | Per-host Memory includes discovered_hosts, open_ports, credentials_found | `/hosts` shows new fields populated after recon results |
| FR-C2-04 | Pluggable LLM backend via `configs/llm.yaml` | Change `model:` to an Ollama model; brain routes via LiteLLM |
| FR-C2-05 | Skills library in version-controlled text files | `c2/skills/system.md` and `recon.md` loaded at startup; not hardcoded |
| FR-KC-02 (partial) | C2 autonomously issues ARP discovery commands | DISPATCHED log appears after REGISTERED with no manual intervention |
| NFR-REP-01 | Unique run_id; all LLM prompts/completions logged with timestamps | `runs/<run_id>/trace.jsonl` contains `llm_prompt` + `llm_completion` events |
| NFR-REP-03 | All prompts in version-controlled files | Skills in `c2/skills/*.md`; `brain.py` has no hardcoded prompt strings |

---

## Files Produced / Modified

```
AgentWorm/
├── configs/
│   └── llm.yaml               # NEW: LLM backend config
├── runs/                       # NEW: volume for per-run trace logs
├── c2/
│   ├── brain.py               # NEW: LLM reasoning engine
│   ├── skills/
│   │   ├── system.md          # NEW: C2 system prompt
│   │   └── recon.md           # NEW: recon skill prompt
│   ├── models.py              # MODIFIED: added discovered_hosts, open_ports, credentials_found
│   ├── main.py                # MODIFIED: BackgroundTasks + brain + run_id
│   └── requirements.txt       # MODIFIED: added litellm, pyyaml
└── docker-compose.yml         # MODIFIED: ANTHROPIC_API_KEY env + configs/ and runs/ volumes
```

---

## Verification Checklist

```bash
# 0. Set API key in your shell before starting
export ANTHROPIC_API_KEY=sk-ant-...

# 1. Rebuild (new dependencies + brain.py)
docker compose down
docker compose up --build

# 2. Watch for autonomous recon dispatch (M-02)
#    DISPATCHED must appear after REGISTERED with NO manual /queue call
docker logs -f agentworm-c2 | grep -E "REGISTERED|BRAIN QUEUED|DISPATCHED|RESULT|LLM"

# 3. After recon results arrive, check discovered_hosts in Memory (M-03)
curl -s http://localhost:8000/hosts | python3 -m json.tool | grep -A10 "discovered_hosts"

# 4. Verify run trace log exists (NFR-REP-01)
#    Get run_id from health endpoint
RUN_ID=$(curl -s http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "Run ID: $RUN_ID"
ls runs/$RUN_ID/

# 5. Inspect trace for LLM events
cat runs/$RUN_ID/trace.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    print(e['ts'], e['event'], e.get('latency_ms',''), str(e.get('completion',''))[:80])
"

# 6. Confirm prompts are on disk, not in code (NFR-REP-03)
grep -n "you are\|issue\|objective" c2/brain.py   # should return nothing
cat c2/skills/system.md
```

**Pass criteria:**
- `DISPATCHED` appears in C2 logs within one beacon cycle of each `REGISTERED` — no `/queue` call made
- `discovered_hosts` in `/hosts` contains at least one IP after ARP results return
- `runs/<run_id>/trace.jsonl` exists with `llm_prompt` and `llm_completion` events, each with a timestamp and `run_id`
- `brain.py` contains no prompt strings — all loaded from `skills/`
