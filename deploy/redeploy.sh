#!/usr/bin/env bash
# Rebuilds and restarts the app after pulling new code. Run as root/sudo.
# Assumes setup.sh has already been run once.
#
# Usage: sudo REPO_DIR=/opt/atc-watch-beta APP_USER=atcwatch ./redeploy.sh

set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/atc-watch-beta}"
APP_USER="${APP_USER:-atcwatch}"

echo "==> Backend: installing any new deps"
cd "$REPO_DIR/backend"
./.venv/bin/pip install -r requirements.txt

echo "==> Frontend: rebuilding"
cd "$REPO_DIR/frontend"
npm ci
npm run build
chown -R "$APP_USER":"$APP_USER" "$REPO_DIR/frontend/dist"

echo "==> Restarting backend service"
systemctl restart atc-watch-backend

echo "==> Reloading Caddy (picks up new static build automatically, this is optional)"
systemctl reload caddy

echo "Done. journalctl -u atc-watch-backend -f to watch logs."
