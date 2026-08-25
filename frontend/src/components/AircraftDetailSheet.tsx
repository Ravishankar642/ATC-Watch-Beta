import type { TrafficAircraft } from "../types/api";
import "./AircraftDetailSheet.css";

interface Props {
  aircraft: TrafficAircraft | null;
  onClose: () => void;
}

export default function AircraftDetailSheet({ aircraft, onClose }: Props) {
  if (!aircraft) return null;

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet__handle" />
        <div className="sheet__header">
          <div className="sheet__callsign mono amber-glow">{aircraft.callsign}</div>
          <div className="sheet__type">{aircraft.aircraft_short ?? "Unknown type"}</div>
        </div>

        <div className="sheet__grid">
          <Stat label="Altitude" value={`${aircraft.altitude.toLocaleString()} ft`} />
          <Stat label="Heading" value={`${String(aircraft.heading).padStart(3, "0")}°`} />
          <Stat label="Groundspeed" value={`${aircraft.groundspeed} kt`} />
          <Stat
            label="Rel. altitude"
            value={
              aircraft.relative_altitude_ft != null
                ? `${aircraft.relative_altitude_ft > 0 ? "+" : ""}${aircraft.relative_altitude_ft.toLocaleString()} ft`
                : "—"
            }
          />
          <Stat label="Distance" value={aircraft.distance_nm != null ? `${aircraft.distance_nm} NM` : "—"} />
          <Stat label="Route" value={`${aircraft.departure ?? "????"} → ${aircraft.arrival ?? "????"}`} />
        </div>

        {aircraft.route && (
          <div className="sheet__route">
            <span className="sheet__route-label">FILED ROUTE</span>
            <span className="mono">{aircraft.route}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value mono">{value}</span>
    </div>
  );
}
