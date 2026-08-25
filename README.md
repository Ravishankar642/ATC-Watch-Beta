# ATC Watch Beta

A VATSIM flight companion PWA: shows your flight and nearby network activity,
and predicts which ATC is actually relevant to your route ahead — with real
iPhone push notifications (installed to the Home Screen, no App Store, no
Apple Developer account).

- **Frontend:** React + TypeScript + Vite, MapLibre GL map, installable PWA
- **Backend:** Python + FastAPI, polls the official VATSIM v3 data feed
- **Push:** Standards-based Web Push with VAPID (works on iOS 16.4+ Safari,
  Android Chrome/Firefox, and desktop browsers)
- **Auth:** VATSIM Connect OAuth — this app never sees your VATSIM password

---

## How it works

- The backend polls `https://data.vatsim.net/v3/vatsim-data.json` every 15
  seconds (matching VATSIM's own feed regeneration cadence) and caches it in
  memory.
- FIR/sector boundaries come from the official
  [VATSpy data project](https://github.com/vatsimnetwork/vatspy-data-project) —
  never invented.
- The **ATC prediction engine** (`backend/app/atc_engine.py`) intersects the
  aircraft's heading-based nearby-track projection with those boundaries,
  applies VATSIM's top-down control convention
  (the most senior *online* facility owns a boundary), and calculates
  distance/ETA to each relevant controller — it does not just alert on
  "nearest controller."
- The **alert tracker** (`backend/app/alert_tracker.py`) keeps a
  per-controller state ledger so the 15-second refresh never re-sends the
  same notification.
- A background job (`backend/app/alert_job.py`) evaluates this for every user
  with notifications enabled and sends Web Push through VAPID — so alerts
  arrive even when the app isn't open.

### Known MVP limitation: route waypoints

Full airway/fix resolution (turning a filed route string like
`DCT ABCDE Y123 FGHIJ DCT` into real waypoint coordinates) requires a navdata
database that's out of scope for this MVP. `route_resolver.py` resolves
departure/arrival airports from a small bundled reference table. Until full
navdata is added, prediction **honestly falls back** to a great-circle
projection along the current heading — it never represents a direct line to
the destination as the filed route or fabricates a route on the map. See
the Roadmap section for how to extend this with full navdata.

---

## Project layout

```
atc-watch-beta/
├── backend/            FastAPI app
│   ├── app/
│   │   ├── main.py             entrypoint, startup/shutdown
│   │   ├── config.py           env-driven settings
│   │   ├── models.py           SQLAlchemy models
│   │   ├── vatsim_client.py    VATSIM v3 feed poller/cache
│   │   ├── vatspy_data.py      FIR/sector boundary loader
│   │   ├── atc_engine.py       ATC relevance/prediction engine
│   │   ├── alert_tracker.py    notification debounce/state
│   │   ├── alert_job.py        background push loop
│   │   ├── push.py             VAPID Web Push sending
│   │   ├── auth.py             VATSIM Connect OAuth
│   │   ├── route_resolver.py   best-effort route geocoding
│   │   └── routers/            auth, flight, atc, traffic, push, settings
│   ├── scripts/generate_vapid_keys.py
│   └── requirements.txt
├── frontend/           React PWA
│   ├── src/
│   │   ├── sw.ts               service worker (push + notificationclick)
│   │   ├── App.tsx, main.tsx
│   │   ├── screens/             LiveMap, AtcAhead, Traffic, FlightDetails, Settings
│   │   ├── components/          Map, TopBar, BottomNav, AircraftDetailSheet
│   │   └── services/            api.ts, push.ts
│   ├── vite.config.ts           PWA manifest + injectManifest service worker
│   └── package.json
└── docker-compose.yml  local Postgres
```

---

## Local development

### 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for local Postgres) — or any Postgres 14+ instance

### 2. Database

```bash
docker compose up -d postgres
```

### 3. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python scripts/generate_vapid_keys.py   # paste output into .env

# Register an app at https://auth.vatsim.net (Sandbox environment is fine for
# dev) and put the client id/secret in .env as well:
#   VATSIM_CLIENT_ID=...
#   VATSIM_CLIENT_SECRET=...
#   VATSIM_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/callback

uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on first startup (`init_db()` in
`main.py`). For production, replace this with proper Alembic migrations
(`alembic init` is already listed as a dependency).

### 4. Frontend

```bash
cd frontend
npm install
cp .env.example .env    # defaults are fine for local dev (Vite proxies /api)
npm run dev
```

Open `http://localhost:5173`.

> **iOS push notifications cannot be tested on `localhost`.** Web Push on
> iOS requires the app to be installed to the Home Screen from a page served
> over HTTPS with a real (or trusted local) certificate — see Deployment
> below, or use a tool like `ngrok`/`cloudflared` to tunnel HTTPS to your dev
> server for on-device testing.

---

## Deployment (HTTPS required)

### Vercel

This repository can be deployed as one Vercel project. Import the repository,
leave the project root at the repository root, and add the following
environment variables from `backend/.env.example`: `DATABASE_URL`,
`SECRET_KEY`, VATSIM OAuth settings, VAPID settings, `FRONTEND_BASE_URL`,
`BACKEND_BASE_URL`, `CORS_ORIGINS`, `CRON_SECRET`, and `SERVERLESS=true`.

Use a managed Postgres database (for example Vercel Postgres, Neon, or Supabase)
for `DATABASE_URL`; the local Docker database is not available on Vercel.
Set both public base URLs to the deployed HTTPS URL and register
`https://YOUR-DOMAIN/api/auth/callback` with VATSIM Connect. The included Vercel
Cron route refreshes the VATSIM feed and sends alerts once per minute. Confirm
that your Vercel plan supports this cron schedule before relying on alerts.

1. **Backend:** deploy `backend/` to any host that can run a long-lived
   ASGI process (the background poll loop and push job need to keep
   running — this rules out pure serverless/functions-per-request hosts
   unless you separate the poller into its own worker). Put a reverse proxy
   (nginx/Caddy) or your platform's load balancer in front for HTTPS.
   Set all `.env` values as real environment variables — **never commit
   `.env`**.
2. **Frontend:** `npm run build` produces `frontend/dist/` — a static PWA.
   Deploy it to any static host (Vercel, Netlify, Cloudflare Pages, S3+CDN,
   or served directly by your reverse proxy) behind HTTPS. Set
   `VITE_API_BASE_URL` to your backend's public HTTPS origin before
   building.
3. **VATSIM Connect:** register a production application at
   https://auth.vatsim.net and update `VATSIM_CLIENT_ID` /
   `VATSIM_CLIENT_SECRET` / `VATSIM_OAUTH_REDIRECT_URI` /
   `settings.FRONTEND_BASE_URL` to your real domains.
4. **CORS:** set `CORS_ORIGINS` in the backend `.env` to your frontend's
   real HTTPS origin.
5. **Database:** point `DATABASE_URL` at your production Postgres instance.

### Installing on iPhone

1. Open the deployed HTTPS URL in **Safari** (not Chrome — iOS requires
   Safari for the Add to Home Screen / installable-PWA flow).
2. Tap the **Share** icon → **Add to Home Screen**.
3. Open the app from the **Home Screen icon** (not the browser tab) —
   push notifications only work from the installed, standalone app.
4. In the app, go to **Settings → Enable Notifications** and tap the
   button (this must be a direct tap; iOS silently ignores permission
   requests not triggered by a user gesture, which is why this app only
   asks after that explicit tap).

---

## Debugging ATC-alert behavior

- `GET /api/debug/state` — last VATSIM feed update time, staleness, pilot/
  controller counts, poll interval.
- `GET /api/atc/ahead` — for the logged-in user: current controller,
  upcoming controllers with the `reason` field explaining why each was
  selected (which boundary, top-down rank, entry distance).
- Backend logs (`uvicorn` stdout) log every VATSIM snapshot refresh and every
  alert sent, including which controller/alert-type fired.

---

## Roadmap (post-MVP)

- Full navdata integration (X-Plane `earth_fix.dat`/`earth_awy.dat` or a
  NASR/DFS extract) to resolve named fixes and airways into real waypoints,
  replacing the current airport-only + projected-track fallback.
- PC simulator bridge: `route_resolver`/`vatsim_client` are structured so a
  future Windows companion app can `POST` higher-frequency MSFS/X-Plane
  position updates to a new endpoint, feeding the same ATC engine and map
  without changing its interface.
- Traffic clustering for very dense airspace (the traffic endpoint already
  supports radius/altitude server-side filtering; client-side clustering at
  low zoom is the next step for extreme-density areas like major hubs).
- Replace `init_db()`'s `create_all` with versioned Alembic migrations
  before any production schema change.

---

## Security notes

- VATSIM credentials are never stored — only VATSIM Connect OAuth tokens are
  exchanged server-side, and only the resulting session cookie (HttpOnly,
  Secure in production, signed with `SECRET_KEY`) is stored client-side.
- The VAPID private key never leaves the backend; only the public key is
  exposed via `/api/push/vapid-public-key`.
- All settings/push endpoints require an authenticated session.
- Push subscriptions that return `404`/`410` (expired/unsubscribed) are
  automatically pruned from the database.
