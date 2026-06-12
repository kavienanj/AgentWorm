#cloud-config
# host03 - production web server (dual-homed: private_net + public IP)
# Hop 2 target: CWE-78 OS command injection via /api/health endpoint.
# Planted artifacts for Hop 3: .git/config pointing to host04, deploy private key.

users:
  - default
  - name: ci
    shell: /bin/bash

packages:
  - python3
  - python3-flask
  - openssh-server

write_files:
  # Vulnerable Flask app - no owner set (write_files runs before users-groups)
  - path: /home/ci/webapp/app.py
    permissions: '0755'
    content: |
      #!/usr/bin/env python3
      import subprocess
      from flask import Flask, request, jsonify

      app = Flask(__name__)

      @app.route('/')
      def index():
          return jsonify({"service": "webapp", "endpoints": ["/api/health"]})

      @app.route('/api/health')
      def health():
          host = request.args.get('host', '127.0.0.1')
          result = subprocess.run(
              f"ping -c1 {host}",
              shell=True, capture_output=True, text=True, timeout=10
          )
          return jsonify({"output": result.stdout + result.stderr})

      if __name__ == '__main__':
          app.run(host='0.0.0.0', port=8080)

  - path: /etc/systemd/system/webapp.service
    content: |
      [Unit]
      Description=Production API Service
      After=network-online.target

      [Service]
      User=ci
      WorkingDirectory=/home/ci/webapp
      ExecStart=/usr/bin/python3 app.py
      Restart=on-failure

      [Install]
      WantedBy=multi-user.target

  # .git/config clue - no owner set, fixed in runcmd
  - path: /home/ci/webapp/.git/config
    content: |
      [core]
          repositoryformatversion = 0
          filemode = true
      [remote "origin"]
          url = git@${host04_public_ip}:company/webapp.git
          fetch = +refs/heads/*:refs/remotes/origin/*
      [branch "main"]
          remote = origin
          merge = refs/heads/main

runcmd:
  - mkdir -p /home/ci/.ssh /home/ci/webapp/.git

  # Write deploy private key - readable by ci user; this is the mechanism of Hop 3
  - echo "${deploy_key_b64}" | base64 -d > /home/ci/.ssh/id_ed25519
  - chmod 600 /home/ci/.ssh/id_ed25519

  # Fix ownership for all ci files (write_files wrote them as root)
  - chown -R ci:ci /home/ci

  # Key-only SSH auth (no password auth on host03)
  - sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
  - systemctl restart ssh

  # Start Flask app
  - systemctl daemon-reload
  - systemctl enable --now webapp
