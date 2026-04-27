#!/usr/bin/env bash
# Stand up the MyLittleAnsible SSH sandbox on localhost:2222.
#
# Generates an ed25519 key pair on first run, builds the image,
# starts the container, and waits until sshd is ready.

set -euo pipefail
cd "$(dirname "$0")"

# Pick whichever docker compose flavour is available.
if docker compose version >/dev/null 2>&1; then
    DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    DC=(docker-compose)
else
    echo "error: neither 'docker compose' nor 'docker-compose' is installed" >&2
    exit 1
fi

if [[ ! -f id_mla ]]; then
    echo "[setup] generating ed25519 key pair (sandbox/id_mla, sandbox/id_mla.pub)"
    ssh-keygen -t ed25519 -N "" -f id_mla -C "mla-sandbox" >/dev/null
fi
chmod 600 id_mla
chmod 644 id_mla.pub

echo "[setup] building & starting sandbox container"
"${DC[@]}" up -d --build

# Drop any stale host key for localhost:2222 so paramiko's
# AutoAddPolicy does not clash with an old known_hosts entry.
ssh-keygen -R "[127.0.0.1]:2222" >/dev/null 2>&1 || true

echo "[setup] waiting for sshd to accept logins on localhost:2222..."
# We need more than just "port open" — systemd boots for a while and
# blocks logins via pam_nologin until multi-user.target is reached.
for _ in $(seq 1 60); do
    if ssh -i id_mla -p 2222 \
           -o StrictHostKeyChecking=no \
           -o UserKnownHostsFile=/dev/null \
           -o LogLevel=ERROR \
           -o ConnectTimeout=3 \
           -o BatchMode=yes \
           mla@127.0.0.1 'true' >/dev/null 2>&1; then
        echo "[setup] sandbox accepts logins"
        break
    fi
    sleep 2
done

cat <<'EOF'

Sandbox is ready.

    inventory  : examples/inventory-sandbox.yml
    host       : 127.0.0.1:2222
    user       : mla  (passwordless sudo)
    key file   : sandbox/id_mla

Try it:
    python -m mla -f examples/tasks.yml            -i examples/inventory-sandbox.yml --dry-run
    python -m mla -f examples/modules/apt.yml      -i examples/inventory-sandbox.yml
    python -m mla -f examples/modules/file.yml     -i examples/inventory-sandbox.yml
    python -m mla -f examples/modules/service.yml  -i examples/inventory-sandbox.yml

Tear down with:
    ./sandbox/teardown.sh
EOF
