#!/bin/bash
# MOTUS Web Tunnel — keeps the web interface publicly accessible
PORT=${1:-8848}
SUB=${2:-motus-agent}

echo "Starting MOTUS tunnel on port $PORT..."

ssh -T \
  -o StrictHostKeyChecking=no \
  -o PubkeyAuthentication=no \
  -o ConnectTimeout=10 \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=3 \
  -p 443 \
  -R0:localhost:$PORT \
  a.pinggy.io 2>&1 | while IFS= read -r line; do
    echo "[$(date +%H:%M:%S)] $line"
    if echo "$line" | grep -q "https://.*pinggy-free.link"; then
      echo ">>> PUBLIC URL: $line" | tee /tmp/motus_public_url.txt
    fi
done
