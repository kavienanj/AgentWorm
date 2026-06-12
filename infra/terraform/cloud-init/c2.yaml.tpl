#cloud-config
# C2 server - installs deps, creates symlinks to replicate Docker mount layout,
# writes systemd unit. Code is deployed later by `make deploy`.

packages:
  - python3
  - python3-pip
  - git

write_files:
  - path: /etc/systemd/system/agentworm-c2.service
    content: |
      [Unit]
      Description=AgentWorm C2
      After=network-online.target
      Wants=network-online.target

      [Service]
      WorkingDirectory=/opt/agentworm/c2
      EnvironmentFile=/opt/agentworm/.env
      Environment=MAX_HOSTS=5
      ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
      Restart=on-failure
      RestartSec=5
      StandardOutput=append:/opt/agentworm/logs/agentworm-c2-logs.txt
      StandardError=append:/opt/agentworm/logs/agentworm-c2-logs.txt

      [Install]
      WantedBy=multi-user.target

  # Embed requirements so pip can install before code is deployed
  - path: /opt/agentworm/requirements.txt
    content: |
      fastapi==0.115.5
      uvicorn==0.32.1
      pydantic>=2.11.2
      requests==2.32.3
      pyyaml==6.0.2
      langgraph>=0.2.0
      langchain-openai>=0.2.0
      langchain-anthropic>=0.3.0
      langchain-core>=0.3.0
      langchain-openrouter>=0.1.0

runcmd:
  # Create directory structure
  - mkdir -p /opt/agentworm/runs /opt/agentworm/logs /opt/agentworm/configs

  # Replicate Docker volume mount paths so main.py works unchanged:
  #   /configs/llm.yaml  -> /opt/agentworm/configs/llm.yaml
  #   /runs/<run_id>/    -> /opt/agentworm/runs/<run_id>/
  #   /app/skills/       -> /opt/agentworm/skills/
  #   /app/dba.py        -> /opt/agentworm/dba.py  (created by make deploy)
  - ln -sf /opt/agentworm/configs /configs
  - ln -sf /opt/agentworm/runs /runs
  - ln -sf /opt/agentworm /app

  # Install Python dependencies ahead of first deploy
  - pip3 install -r /opt/agentworm/requirements.txt

  # Enable service - starts on reboot; first start is done by `make deploy`
  - systemctl daemon-reload
  - systemctl enable agentworm-c2
