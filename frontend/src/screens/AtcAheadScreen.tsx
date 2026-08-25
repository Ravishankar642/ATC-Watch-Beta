import { api } from "../services/api";
import { usePolling } from "../hooks/usePolling";
import type { PredictedController } from "../types/api";
import "./AtcAheadScreen.css";

export default function AtcAheadScreen() {
  const { data: atc, loading } = usePolling(() => api.atcAhead(), 15000);

  return (
    <div className="screen atc-screen">
      <header className="screen__header">
        <h1>ATC Ahead</h1>
        {atc?.data_stale && <span className="stale-pill">DATA STALE</span>}
      </header>

      {loading && !atc && <p className="dim">Loading VATSIM data…</p>}

      {atc && !atc.current && atc.upcoming.length === 0 && (
        <div className="empty-state">
          <p>No relevant ATC found along your route.</p>
          <p className="dim">This updates automatically as controllers come online ahead of you.</p>
        </div>
      )}

      {atc?.current && <ControllerRow controller={atc.current} kind="CURRENT" />}
      {atc?.upcoming.map((c) => (
        <ControllerRow key={c.callsign} controller={c} kind="NEXT" />
      ))}
    </div>
  );
}

function ControllerRow({ controller, kind }: { controller: PredictedController; kind: "CURRENT" | "NEXT" }) {
  return (
    <div className={`atc-row ${kind === "CURRENT" ? "atc-row--current" : ""}`}>
      <div className="atc-row__left">
        <span className={`atc-row__kind ${kind === "CURRENT" ? "amber-glow" : ""}`}>{kind}</span>
        <span className="atc-row__callsign mono">{controller.callsign}</span>
      </div>
      <div className="atc-row__right">
        <span className="atc-row__freq mono">{controller.frequency}</span>
        {controller.eta_minutes != null && kind === "NEXT" && (
          <span className="atc-row__eta mono">{Math.round(controller.eta_minutes)} min</span>
        )}
        {controller.distance_nm != null && kind === "NEXT" && controller.eta_minutes == null && (
          <span className="atc-row__eta mono">{Math.round(controller.distance_nm)} NM</span>
        )}
        <span className="status-dot status-dot--online" title="Online" />
      </div>
    </div>
  );
}
