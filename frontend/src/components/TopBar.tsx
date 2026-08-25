import type { MyFlight } from "../types/api";
import "./TopBar.css";

interface Props {
  flight: MyFlight | null;
  currentAtc: string | null;
  currentFreq: string | null;
  dataStale: boolean;
}

export default function TopBar({ flight, currentAtc, currentFreq, dataStale }: Props) {
  const pilot = flight?.pilot;

  return (
    <div className="topbar">
      <div className="topbar__row">
        <div className="topbar__callsign">
          {pilot?.callsign ?? "— — —"}
          {dataStale && <span className="topbar__stale">DATA STALE</span>}
        </div>
        <div className="topbar__atc">
          {currentAtc ? (
            <>
              <span className="green-glow mono">{currentAtc}</span>
              <span className="mono topbar__freq">{currentFreq}</span>
            </>
          ) : (
            <span className="mono" style={{ color: "var(--text-dim)" }}>
              UNICOM / NO ATC
            </span>
          )}
        </div>
      </div>
      <div className="topbar__readouts">
        <Readout label="ALT" value={pilot ? pilot.altitude.toLocaleString() : "----"} unit="ft" />
        <Readout label="GS" value={pilot ? String(pilot.groundspeed) : "---"} unit="kt" />
        <Readout label="HDG" value={pilot ? String(pilot.heading).padStart(3, "0") : "---"} unit="°" />
      </div>
    </div>
  );
}

function Readout({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="readout">
      <span className="readout__label">{label}</span>
      <span className="readout__value amber-glow mono">
        {value}
        <span className="readout__unit">{unit}</span>
      </span>
    </div>
  );
}
