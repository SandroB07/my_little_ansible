#!/usr/bin/env bash
# Stop and remove the MyLittleAnsible SSH sandbox.

set -euo pipefail
cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then
    docker compose down -v
elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose down -v
else
    echo "error: neither 'docker compose' nor 'docker-compose' is installed" >&2
    exit 1
fi
