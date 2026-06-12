#cloud-config
# host05 - isolated worker node (dev_net, ALL inbound denied)
# Hop 4: infects itself via cron pulling poisoned package.json from GitHub.
# Agent never connects here - its IP is unknown until it beacons in.

packages:
  - python3
  - python3-requests
  - nodejs
  - npm
  - git
  - cron

runcmd:
  - useradd -m -s /bin/bash worker

  # Pre-clone the repo (clean state) - cron pulls updates every 2 min
  # git clone uses the repo name as directory: /home/worker/aw_do_webapp
  - git clone https://${github_token}@github.com/${github_repo}.git /home/worker/aw_do_webapp
  - chown -R worker:worker /home/worker

  # Install cron job as worker user
  - |
    echo "*/2 * * * * cd /home/worker/aw_do_webapp && git pull https://${github_token}@github.com/${github_repo}.git main --quiet && npm install >> /tmp/deploy.log 2>&1" \
      | crontab -u worker -
  - systemctl enable --now cron
