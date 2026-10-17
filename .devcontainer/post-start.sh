#!/bin/bash
# postStartCommand: runs on every container start, as the non-root `dev` user.
#   1. Apply database migrations against the compose Postgres.
#   2. Opt-in: lock egress down with init-firewall.sh.
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── 1. Migrations ────────────────────────────────────────────────────────────
# docker-compose.yml already waits for Postgres to be healthy; the retry only
# covers the short window where pg_isready passes before the DB accepts logins.
echo "==> alembic upgrade head"
cd "$WORKSPACE/backend"
for attempt in 1 2 3 4 5; do
  if alembic upgrade head; then
    break
  fi
  if [ "$attempt" -eq 5 ]; then
    echo "ERROR: migrations failed after $attempt attempts"
    exit 1
  fi
  echo "Migration attempt $attempt failed, retrying in 3s..."
  sleep 3
done

# ── 2. Egress firewall (opt-in) ──────────────────────────────────────────────
# Enabled with ARBITER_DEVCONTAINER_FIREWALL=1 on the host (docker-compose.yml
# passes it through). iptables rules do not survive a container restart, so it
# is re-applied on every start. After the first run the container is locked
# (no blanket sudo) and the script can only be re-run with no arguments, which
# re-applies the allowlist persisted on that first run.
if [ "${ARBITER_DEVCONTAINER_FIREWALL:-0}" = "1" ]; then
  echo "==> Enabling default-deny egress firewall"
  if [ -e /etc/sudoers.d/dev-admin ]; then
    # shellcheck disable=SC2086  # intentional word splitting: space-separated list
    sudo /usr/local/bin/init-firewall.sh ${ARBITER_FIREWALL_EXTRA_DOMAINS:-}
  else
    sudo /usr/local/bin/init-firewall.sh
  fi
else
  echo "==> Egress firewall off (set ARBITER_DEVCONTAINER_FIREWALL=1 to enable)"
fi
