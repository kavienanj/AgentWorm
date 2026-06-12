#!/bin/bash
# Poll C2 /health until 200 OK. Called by `make deploy` after starting the service.
set -e

TFDIR="$(dirname "$0")/../terraform"
C2=$(cd "$TFDIR" && terraform output -raw c2_public_ip)

echo "Waiting for C2 at http://$C2:8000/health ..."
for i in $(seq 1 60); do
    if curl -sf --max-time 3 "http://$C2:8000/health" > /dev/null 2>&1; then
        echo "C2 ready."
        exit 0
    fi
    echo "  [$i/60] not ready yet — retrying in 5s"
    sleep 5
done

echo "ERROR: C2 did not become ready after 5 minutes."
exit 1
