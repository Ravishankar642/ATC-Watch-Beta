import { useState } from "react";
import { Link } from "react-router-dom";
import AircraftDetailSheet from "../components/AircraftDetailSheet";
import LiveMap from "../components/LiveMap";
import TopBar from "../components/TopBar";
import { api } from "../services/api";
import { usePolling } from "../hooks/usePolling";
import { isIos, isStandalonePwa } from "../services/push";
import type { TrafficAircraft } from "../types/api";

export default function LiveMapScreen() {
  const { data: flight } = usePolling(() => api.myFlight(), 15000);
  const { data: atc } = usePolling(() => api.atcAhead(), 15000);
  const { data: coverage } = usePolling(() => api.atcCoverage(), 30000);
  // The radar map uses broader, all-altitude traffic than the list screen.
  const { data: traffic } = usePolling(() => api.traffic(300, 60000), 15000);
  const [selected, setSelected] = useState<TrafficAircraft | null>(null);
  const [dismissedInstallBanner, setDismissedInstallBanner] = useState(false);

  const showInstallBanner = isIos() && !isStandalonePwa() && !dismissedInstallBanner;

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <LiveMap flight={flight ?? null} traffic={traffic?.aircraft ?? []} coverage={coverage ?? null} onSelectAircraft={setSelected} />
      <TopBar
        flight={flight ?? null}
        currentAtc={atc?.current?.callsign ?? null}
        currentFreq={atc?.current?.frequency ?? null}
        dataStale={Boolean(flight?.data_stale)}
      />
      {showInstallBanner && (
        <div className="not-connected-banner" style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
          <span>
            Install this app for push alerts — <Link to="/settings" style={{ color: "var(--amber)" }}>see how</Link>
          </span>
          <button onClick={() => setDismissedInstallBanner(true)} style={{ background: "none", border: "none", color: "var(--text-dim)" }}>
            ✕
          </button>
        </div>
      )}
      {flight && !flight.connected && !showInstallBanner && (
        <div className="not-connected-banner">
          Nothing being tracked right now — <Link to="/settings" style={{ color: "var(--amber)" }}>enter a callsign</Link> or connect to VATSIM under your own account.
        </div>
      )}
      <AircraftDetailSheet aircraft={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
