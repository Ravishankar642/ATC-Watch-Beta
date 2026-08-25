import { api } from "../services/api";
import { usePolling } from "../hooks/usePolling";
import { Link } from "react-router-dom";
import "./FlightDetailsScreen.css";

export default function FlightDetailsScreen() {
  const { data: flight, loading } = usePolling(() => api.myFlight(), 15000);

  if (loading && !flight) {
    return (
      <div className="screen">
        <p className="dim">Loading your flight…</p>
      </div>
    );
  }

  if (!flight?.connected || !flight.pilot) {
    return (
      <div className="screen">
        <header className="screen__header">
          <h1>Flight Details</h1>
        </header>
        <div className="empty-state">
          <p>Nothing being tracked right now.</p>
          <p className="dim">
            Go to <Link to="/settings">Settings</Link> and enter a callsign to track — your own flight or anyone
            else currently online.
          </p>
        </div>
      </div>
    );
  }

  const p = flight.pilot;

  return (
    <div className="screen">
      <header className="screen__header">
        <h1>Flight Details</h1>
        {flight.data_stale && <span className="stale-pill">DATA STALE</span>}
      </header>

      <div className="flight-card">
        <div className="flight-card__callsign mono amber-glow">{p.callsign}</div>
        <div className="flight-card__type dim">{p.aircraft_short ?? "Unknown aircraft"}</div>

        <div className="flight-card__route">
          <RoutePoint label="DEP" value={p.departure ?? "????"} />
          <div className="flight-card__route-line" />
          <RoutePoint label="ARR" value={p.arrival ?? "????"} />
        </div>
      </div>

      <div className="detail-grid">
        <DetailStat label="Altitude" value={`${p.altitude.toLocaleString()} ft`} />
        <DetailStat label="Groundspeed" value={`${p.groundspeed} kt`} />
        <DetailStat label="Heading" value={`${String(p.heading).padStart(3, "0")}°`} />
        <DetailStat label="Transponder" value={p.transponder ?? "—"} />
        <DetailStat label="Position" value={`${p.latitude.toFixed(3)}, ${p.longitude.toFixed(3)}`} />
      </div>

      {p.route && (
        <div className="filed-route">
          <span className="filed-route__label">FILED ROUTE</span>
          <p className="mono">{p.route}</p>
        </div>
      )}
    </div>
  );
}

function RoutePoint({ label, value }: { label: string; value: string }) {
  return (
    <div className="route-point">
      <span className="route-point__label">{label}</span>
      <span className="mono route-point__value">{value}</span>
    </div>
  );
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-stat">
      <span className="detail-stat__label">{label}</span>
      <span className="mono detail-stat__value">{value}</span>
    </div>
  );
}
