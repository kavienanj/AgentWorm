.PHONY: infra-up infra-down deploy deploy-dba run setup teardown reset-run \
        logs status trace costs

# Source .env and export TF_VAR_* mappings in a single shell block.
_TF := set -a; . ../.env; set +a; \
       export TF_VAR_do_token=$$DO_TOKEN; \
       export TF_VAR_github_token=$$DO_GITHUB_TOKEN

# SSH identity file — non-default name so must be passed explicitly everywhere.
SSH_KEY := $(HOME)/.ssh/id_ed25519_digitalocean
SSH     := ssh -i $(SSH_KEY) -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
SCP     := scp -i $(SSH_KEY) -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null

# ── Tier 1: Infrastructure (minutes, once per session) ───────────────────────

infra-up:
	@$(_TF); \
	  cd terraform && terraform init -upgrade && terraform apply -auto-approve
	@echo ""
	@echo "Infra up. Next: make deploy"

infra-down:
	@$(_TF); \
	  cd terraform && terraform destroy -auto-approve

# ── Tier 2: Code deployment (seconds, after any code change) ─────────────────

deploy:
	@C2=$$(cd terraform && terraform output -raw c2_public_ip); \
	  H3=$$(cd terraform && terraform output -raw host03_public_ip); \
	  H1_PRIV=$$(cd terraform && terraform output -raw host01_private_ip); \
	  echo "Syncing code to C2..."; \
	  rsync -av --delete -e "$(SSH)" ../c2 ../dba ../configs root@$$C2:/opt/agentworm/; \
	  rsync -av -e "$(SSH)" ../.env root@$$C2:/opt/agentworm/.env; \
	  echo "Injecting C2_PUBLIC_IP=$$C2 into .env on C2..."; \
	  $(SSH) root@$$C2 "grep -q '^C2_PUBLIC_IP=' /opt/agentworm/.env \
	    && sed -i 's|^C2_PUBLIC_IP=.*|C2_PUBLIC_IP='$$C2'|' /opt/agentworm/.env \
	    || echo 'C2_PUBLIC_IP='$$C2 >> /opt/agentworm/.env"; \
	  echo "Creating symlinks and restarting C2..."; \
	  $(SSH) root@$$C2 'ln -sf /opt/agentworm/dba/agent.py /opt/agentworm/dba.py \
	    && ln -sf /opt/agentworm/c2/skills /opt/agentworm/skills \
	    && systemctl daemon-reload && systemctl restart agentworm-c2'; \
	  echo "Pushing DBA to host01..."; \
	  $(SCP) -o ConnectTimeout=10 \
	    -o "ProxyCommand=$(SSH) root@$$H3 -W %h:%p" \
	    ../dba/agent.py root@$$H1_PRIV:/opt/sysmon/monitor.py \
	    || echo "WARN: host01 not reachable yet — run 'make deploy-dba' when ready"
	./scripts/await-ready.sh
	@echo "Deployed. Next: make run"

deploy-dba:
	@H3=$$(cd terraform && terraform output -raw host03_public_ip); \
	  H1_PRIV=$$(cd terraform && terraform output -raw host01_private_ip); \
	  $(SCP) -o "ProxyCommand=$(SSH) root@$$H3 -W %h:%p" \
	    ../dba/agent.py root@$$H1_PRIV:/opt/sysmon/monitor.py
	@echo "DBA updated on host01."

# ── Tier 3: Experiment runs (45s, before every run) ──────────────────────────

run:
	./scripts/run.sh

# ── Convenience composites ────────────────────────────────────────────────────

setup:
	$(MAKE) infra-up
	$(MAKE) deploy
	$(MAKE) run

teardown:
	$(MAKE) infra-down

reset-run: run   # backward-compat alias

# ── Observability ─────────────────────────────────────────────────────────────

logs:
	@C2=$$(cd terraform && terraform output -raw c2_public_ip); \
	  $(SSH) root@$$C2 'tail -f /opt/agentworm/logs/agentworm-c2-logs.txt \
	    | grep -iE "REGISTERED|milestone|TOOL_CALL|TOOL_RESULT|AGENT_TURN"'

trace:
	@C2=$$(cd terraform && terraform output -raw c2_public_ip); \
	  RUN=$$(curl -s http://$$C2:8000/health \
	    | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])"); \
	  $(SSH) root@$$C2 "cat /opt/agentworm/runs/$$RUN/trace.jsonl"

status:
	@C2=$$(cd terraform && terraform output -raw c2_public_ip); \
	  curl -s http://$$C2:8000/metrics | python3 -m json.tool

costs:
	@C2=$$(cd terraform && terraform output -raw c2_public_ip); \
	  python3 -c "\
import urllib.request, json, datetime; \
h=json.loads(urllib.request.urlopen('http://$$C2:8000/health').read()); \
up=datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(h['started_at']); \
print(f'Uptime: {str(up).split(chr(46))[0]}   Est. cost: \$${up.total_seconds()/3600*0.063:.3f}')"
