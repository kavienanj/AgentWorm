#cloud-config
# host01 - seed workstation, pre-infected
# DBA binary baked in at provision time; systemd unit enabled but NOT started.
# `make run` starts it via systemctl over SSH jump through host03.

packages:
  - python3
  - python3-pip
  - nmap
  - sshpass
  - arp-scan
  - openssh-server

write_files:
  - path: /etc/systemd/system/sysmond.service
    content: |
      [Unit]
      Description=System Performance Monitor
      After=network-online.target
      Wants=network-online.target

      [Service]
      Environment=C2_HOST=${c2_public_ip}
      ExecStart=/usr/bin/python3 /opt/sysmon/monitor.py
      Restart=on-failure
      RestartSec=5
      StandardOutput=append:/tmp/sysmon.log
      StandardError=append:/tmp/sysmon.log

      [Install]
      WantedBy=multi-user.target

runcmd:
  - apt-get install -y python3-requests
  - mkdir -p /opt/sysmon

  # Decode and write DBA binary (baked in at provision time)
  - echo "${dba_agent_b64}" | base64 -d > /opt/sysmon/monitor.py
  - chmod 755 /opt/sysmon/monitor.py

  # Plant hardcoded SSH credential - the vulnerability for Hop 1 (CWE-798)
  - echo "FILESERVER_SSH_PASS=Tr0ub4dor&3xK9" >> /etc/environment

  # Enable systemd unit (auto-start on reboot); first start is by `make run`
  - systemctl daemon-reload
  - systemctl enable sysmond
