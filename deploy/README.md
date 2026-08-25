# Deploying on Ubuntu (self-hosted, e.g. Oracle Cloud)

This app needs a **long-lived process** (the VATSIM poll loop + push alert
job run as background tasks inside the backend — see `app/main.py`), so it
must run as a real service, not behind an ephemeral/serverless invocation
model. On plain `uvicorn` with no reverse proxy, two things are usually
broken:

1. **No HTTPS** — iOS Safari refuses `Notification.requestPermission()` /
   `PushManager.subscribe()` on any origin that isn't real, trusted HTTPS.
   Plain HTTP (or a self-signed cert) silently fails, even after the app is
   installed to the Home Screen.
2. Frontend/backend served from different origins/ports without CORS or
   proxying configured correctly.

`setup.sh` fixes both by putting **Caddy** in front as a reverse proxy that
gets you free, automatic HTTPS (Let's Encrypt) with no manual certbot steps,
and proxies `/api/*` to the backend on the same origin the frontend is
served from.

## One-time setup

You need a real domain name pointed (A/AAAA record) at this server's public
IP before running this — Caddy can't get a certificate otherwise.

```bash
git clone <your-repo-url> /opt/atc-watch-beta   # or unzip the project there
cd /opt/atc-watch-beta
sudo DOMAIN=atc.example.com ./deploy/setup.sh
```

This installs Python, Node, Postgres, and Caddy; creates a `vatsim_atc_watch`
Postgres database; builds the backend venv and frontend static bundle;
generates a `backend/.env` with a random `SECRET_KEY` and a fresh VAPID
keypair if one doesn't already exist; and installs/starts two systemd
services: `atc-watch-backend` and `caddy`.

**After it finishes**, you still need to:

- Register an app at https://auth.vatsim.net and put `VATSIM_CLIENT_ID` /
  `VATSIM_CLIENT_SECRET` into `backend/.env` (redirect URI:
  `https://YOUR-DOMAIN/api/auth/callback`), then
  `sudo systemctl restart atc-watch-backend`.
- **Oracle Cloud specific:** open TCP 80 and 443 in the VCN's *Security
  List* or *Network Security Group* in the OCI console. `ufw` alone is not
  enough on OCI — the cloud network layer blocks these ports by default
  regardless of the host firewall.

## Redeploying after code changes

```bash
cd /opt/atc-watch-beta
git pull
sudo ./deploy/redeploy.sh
```

## Checking it's working

```bash
systemctl status atc-watch-backend
journalctl -u atc-watch-backend -f      # backend logs, incl. VATSIM refresh + alerts sent
journalctl -u caddy -f                  # HTTPS/proxy logs
curl -s https://YOUR-DOMAIN/api/health  # should return JSON, not an error
```

On iPhone: open `https://YOUR-DOMAIN` in **Safari**, Share → **Add to Home
Screen**, open the app from that Home Screen icon (not the browser tab),
then Settings → **Enable Notifications**.
