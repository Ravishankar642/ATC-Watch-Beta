import { useState } from "react";
import AircraftDetailSheet from "../components/AircraftDetailSheet";
import { api } from "../services/api";
import { usePolling } from "../hooks/usePolling";
import type { TrafficAircraft } from "../types/api";
import "./TrafficScreen.css";

export default function TrafficScreen() {
  const [radiusNm, setRadiusNm] = useState(150);
  const [altDiffFt, setAltDiffFt] = useState(10000);
  const { data: traffic, loading } = usePolling(() => api.traffic(radiusNm, altDiffFt), 15000);
  const [selected, setSelected] = useState<TrafficAircraft | null>(null);

  return (
    <div className="screen traffic-screen">
      <header className="screen__header">
        <h1>Traffic</h1>
        {traffic?.data_stale && <span className="stale-pill">DATA STALE</span>}
      </header>

      <div className="filter-row">
        <FilterChip label="Radius" value={`${radiusNm} NM`} onCycle={() => setRadiusNm(cycleRadius(radiusNm))} />
        <FilterChip label="Alt diff" value={`±${(altDiffFt / 1000).toFixed(0)}k ft`} onCycle={() => setAltDiffFt(cycleAlt(altDiffFt))} />
      </div>

      {loading && !traffic && <p className="dim">Loading traffic…</p>}

      {traffic && traffic.aircraft.length === 0 && (
        <div className="empty-state">
          <p>No traffic within {radiusNm} NM / ±{altDiffFt.toLocaleString()} ft.</p>
        </div>
      )}

      {traffic?.aircraft.map((ac) => (
        <button key={ac.callsign} className="traffic-item" onClick={() => setSelected(ac)}>
          <div className="traffic-item__left">
            <span className="mono traffic-item__callsign">{ac.callsign}</span>
            <span className="dim">{ac.aircraft_short ?? "—"} · {ac.departure ?? "????"}→{ac.arrival ?? "????"}</span>
          </div>
          <div className="traffic-item__right">
            <span className="mono">{Math.round(ac.altitude / 100)
              .toString()
              .padStart(3, "0")}</span>
            <span className="dim mono">{ac.distance_nm != null ? `${ac.distance_nm} NM` : "—"}</span>
          </div>
        </button>
      ))}

      <AircraftDetailSheet aircraft={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function FilterChip({ label, value, onCycle }: { label: string; value: string; onCycle: () => void }) {
  return (
    <button className="filter-chip" onClick={onCycle}>
      <span className="filter-chip__label">{label}</span>
      <span className="mono">{value}</span>
    </button>
  );
}

function cycleRadius(current: number): number {
  const steps = [50, 100, 150, 250, 500];
  const idx = steps.indexOf(current);
  return steps[(idx + 1) % steps.length];
}

function cycleAlt(current: number): number {
  const steps = [2000, 5000, 10000, 20000, 60000];
  const idx = steps.indexOf(current);
  return steps[(idx + 1) % steps.length];
}
