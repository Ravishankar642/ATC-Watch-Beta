#!/usr/bin/env bash
#
# ATC Watch Beta — Ubuntu 24.04 deployment script.
#
# What this does:
#   1. Installs system packages: Python 3.12, Node.js 20, Postgres 16, Caddy.
#   2. Creates a Postgres user/database for the app.
#   3. Builds the Python venv + installs backend deps.
#   4. Builds the frontend static bundle.
#   5. Installs systemd units for the backend (long-lived uvicorn process,
#      required — this app runs a background poll loop + push job, it is
#      NOT a request-per-invocation serverless app) and Caddy as the HTTPS
#      reverse proxy + static file server.
#
# What this does NOT do for you:
#   - Point a real domain's DNS A/AAAA record at this server's public IP.
#     Caddy's automatic HTTPS (Let's Encrypt) will fail without that.
#   - Fill in backend/.env with real secrets (SECRET_KEY, VATSIM OAuth
#     client id/secret, VAPID keys, DATABASE_URL password if you change it).
#   - Open port 80/443 in your cloud firewall/security list (Oracle Cloud:
#     do this in the VCN's Security List / Network Security Group, not just
#     ufw — Oracle blocks these ports at the cloud level by default).
#
# Usage:
#   sudo REPO_DIR=/opt/atc-watch-beta DOMAIN=atc.example.com ./setup.sh
#
# Re-running this script is safe (idempotent-ish) for re-deploys after a
# `git pull` — it will rebuild and restart services.

set -euo pipefail

# ---- Configuration (override via env vars when invoking) ------------------
REPO_DIR="${REPO_DIR:-/opt/atc-watch-beta}"
DOMAIN="${DOMAIN:-}"                 # e.g. atc.example.com — REQUIRED for HTTPS
APP_USER="${APP_USER:-atcwatch}"     # unprivileged system user the app runs as
PG_DB="${PG_DB:-vatsim_atc_watch}"
PG_USER="${PG_USER:-vatsim}"
PG_PASSWORD="${PG_PASSWORD:-$(openssl rand -hex 16)}"
NODE_MAJOR="${NODE_MAJOR:-20}"

if [[ $EUID -ne 0 ]]; then
  echo "Run this with sudo/as root (it installs system packages and creates a system user)." >&2
  exit 1
fi

if [[ -z "$DOMAIN" ]]; then
  echo "DOMAIN is required, e.g.:  sudo DOMAIN=atc.example.com ./setup.sh" >&2
  echo "(Caddy needs a real domain pointed at this server to obtain an HTTPS cert.)" >&2
  exit 1
fi

echo "==> Deploying ATC Watch Beta"
echo "    repo dir : $REPO_DIR"
echo "    domain   : $DOMAIN"
echo "    app user : $APP_USER"
echo

# ---- 1. System packages ----------------------------------------------------
echo "==> Installing system packages"
apt-get update -y
apt-get install -y \
  python3.12 python3.12-venv python3-pip \
  postgresql postgresql-contrib \
  curl git build-essential ca-certificates gnupg ufw

# Node.js 20 via NodeSource (Ubuntu 24.04's default apt Node is too old)
if ! command -v node >/dev/null || [[ "$(node -v | sed 's/^v//' | cut -d. -f1)" -lt "$NODE_MAJOR" ]]; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
fi

# Caddy (official apt repo) — gives automatic HTTPS via Let's Encrypt
if ! command -v caddy >/dev/null; then
  apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -y
  apt-get install -y caddy
fi

# ---- 2. App system user + repo location ------------------------------------
echo "==> Creating app user and directories"
id -u "$APP_USER" &>/dev/null || useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$REPO_DIR"

if [[ ! -d "$REPO_DIR/.git" && ! -d "$REPO_DIR/backend" ]]; then
  echo "!! $REPO_DIR does not look like the app repo (no backend/ found)."
  echo "!! Copy/clone the project there first, e.g.:"
  echo "     git clone <your-repo-url> $REPO_DIR"
  echo "   or unzip the project archive into $REPO_DIR, then re-run this script."
  exit 1
fi

# ---- 3. Postgres ------------------------------------------------------------
echo "==> Configuring Postgres"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${PG_USER}'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE ${PG_USER} WITH LOGIN PASSWORD '${PG_PASSWORD}';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${PG_DB}'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"

# ---- 4. Backend: venv + deps ------------------------------------------------
echo "==> Setting up backend Python environment"
cd "$REPO_DIR/backend"
python3.12 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

if [[ ! -f .env ]]; then
  echo "==> No backend/.env found — creating one from .env.example"
  cp .env.example .env
  VAPID_OUT="$(./.venv/bin/python scripts/generate_vapid_keys.py)"
  VAPID_PUB="$(echo "$VAPID_OUT" | grep -oP '(?<=VAPID_PUBLIC_KEY=).*')"
  VAPID_PRIV="$(echo "$VAPID_OUT" | grep -oP '(?<=VAPID_PRIVATE_KEY=).*')"
  SECRET_KEY_VAL="$(openssl rand -hex 32)"

  sed -i \
    -e "s#^ENV=.*#ENV=production#" \
    -e "s#^SECRET_KEY=.*#SECRET_KEY=${SECRET_KEY_VAL}#" \
    -e "s#^BACKEND_BASE_URL=.*#BACKEND_BASE_URL=https://${DOMAIN}#" \
    -e "s#^FRONTEND_BASE_URL=.*#FRONTEND_BASE_URL=https://${DOMAIN}#" \
    -e "s#^CORS_ORIGINS=.*#CORS_ORIGINS=[\"https://${DOMAIN}\"]#" \
    -e "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@localhost:5432/${PG_DB}#" \
    -e "s#^VATSIM_OAUTH_REDIRECT_URI=.*#VATSIM_OAUTH_REDIRECT_URI=https://${DOMAIN}/api/auth/callback#" \
    -e "s#^VAPID_PUBLIC_KEY=.*#VAPID_PUBLIC_KEY=${VAPID_PUB}#" \
    -e "s#^VAPID_PRIVATE_KEY=.*#VAPID_PRIVATE_KEY=${VAPID_PRIV}#" \
    .env

  echo
  echo "    Generated backend/.env with a new SECRET_KEY, VAPID keypair, and a"
  echo "    Postgres password (saved in the DATABASE_URL line)."
  echo "    !! You STILL need to fill in VATSIM_CLIENT_ID / VATSIM_CLIENT_SECRET"
  echo "       from https://auth.vatsim.net before OAuth login will work."
  echo
else
  echo "==> backend/.env already exists — leaving it as-is (not overwriting)."
  echo "    Make sure BACKEND_BASE_URL/FRONTEND_BASE_URL/CORS_ORIGINS/"
  echo "    VATSIM_OAUTH_REDIRECT_URI point at https://${DOMAIN}, and that"
  echo "    VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY are set."
fi

chown -R "$APP_USER":"$APP_USER" "$REPO_DIR/backend"
chmod 600 "$REPO_DIR/backend/.env"

# ---- 5. Frontend: build ------------------------------------------------------
echo "==> Building frontend"
cd "$REPO_DIR/frontend"
cat > .env.production <<EOF
# Left empty: Caddy proxies /api/* on the same origin as the frontend, so
# relative fetches from api.ts (BASE = "") work without a separate host.
VITE_API_BASE_URL=
EOF
npm ci
npm run build
chown -R "$APP_USER":"$APP_USER" "$REPO_DIR/frontend/dist"

# ---- 6. systemd unit for backend --------------------------------------------
echo "==> Installing systemd service"
cat > /etc/systemd/system/atc-watch-backend.service <<EOF
[Unit]
Description=ATC Watch Beta backend (FastAPI/uvicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${REPO_DIR}/backend
EnvironmentFile=${REPO_DIR}/backend/.env
# Single worker: the VATSIM poll loop + alert job run as in-process
# background tasks (see app/main.py lifespan). Running multiple uvicorn
# workers would run multiple independent copies of that loop, spamming
# duplicate push notifications. Scale by giving this one process more
# resources, not more workers.
ExecStart=${REPO_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable atc-watch-backend
systemctl restart atc-watch-backend

# ---- 7. Caddy (HTTPS reverse proxy + static frontend) -----------------------
echo "==> Configuring Caddy"
sed -e "s#YOUR-DOMAIN#${DOMAIN}#g" \
    -e "s#/var/www/atc-watch-beta/frontend-dist#${REPO_DIR}/frontend/dist#g" \
    "${REPO_DIR}/deploy/Caddyfile.example" > /etc/caddy/Caddyfile

systemctl enable caddy
systemctl restart caddy

# ---- 8. Firewall (host-level; see note about cloud-level rules above) ------
echo "==> Configuring ufw (host firewall)"
ufw allow OpenSSH || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw --force enable || true

echo
echo "==================================================================="
echo " Done."
echo
echo " Backend service : systemctl status atc-watch-backend"
echo " Backend logs    : journalctl -u atc-watch-backend -f"
echo " Caddy logs      : journalctl -u caddy -f"
echo
echo " Next steps:"
echo "  1. Confirm DNS: ${DOMAIN} must resolve to this server's public IP."
echo "  2. If this is Oracle Cloud: open ports 80 and 443 in the VCN's"
echo "     Security List / Network Security Group (ufw alone isn't enough"
echo "     on OCI — it blocks at the cloud network layer too)."
echo "  3. Edit ${REPO_DIR}/backend/.env and fill in VATSIM_CLIENT_ID /"
echo "     VATSIM_CLIENT_SECRET from https://auth.vatsim.net, using redirect"
echo "     URI https://${DOMAIN}/api/auth/callback, then:"
echo "       systemctl restart atc-watch-backend"
echo "  4. Visit https://${DOMAIN} — Caddy should present a valid Let's"
echo "     Encrypt certificate automatically within a few seconds."
echo "  5. On iPhone: open that https:// URL in Safari, Share -> Add to"
echo "     Home Screen, open from the Home Screen icon, then Settings ->"
echo "     Enable Notifications."
echo "==================================================================="
