#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root="$(pwd -P)"
run_id="final-10022-iwass-v1"
container_name="iwass-final-10022-v1"

# Explicit network isolation and least privilege; NEVER use --network host.
# The entrypoint installs container-local egress restrictions and drops
# privileges before executing untrusted browser content.
docker run --detach \
    --name "$container_name" \
    --restart no \
    --network bridge \
    --dns 1.1.1.1 --dns 9.9.9.9 \
    --read-only \
    --tmpfs /tmp:size=512m,mode=1777 \
    --shm-size 512m \
    --memory 6g \
    --cpus 2 \
    --pids-limit 256 \
    --cap-drop ALL \
    --cap-add NET_ADMIN \
    --cap-add SETUID --cap-add SETGID --cap-add SETPCAP \
    --security-opt no-new-privileges \
    --mount "type=bind,src=$root/data/input,dst=/work/data/input,readonly" \
    --mount "type=bind,src=$root/runs,dst=/work/runs" \
    iwass-scanner:1.0.3 \
    /work/scripts/run_parallel.py \
    /work/data/input/iwss-tranco-it-2026-07-08.csv \
    --run-id "$run_id" --workers 2

echo "Started $container_name"
echo "Progress: $root/runs/$run_id/progress.json"
echo "Log: docker logs $container_name"
