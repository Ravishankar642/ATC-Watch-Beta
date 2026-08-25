import { useEffect } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import BottomNav from "./components/BottomNav";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import AtcAheadScreen from "./screens/AtcAheadScreen";
import FlightDetailsScreen from "./screens/FlightDetailsScreen";
import LiveMapScreen from "./screens/LiveMapScreen";
import LoginScreen from "./screens/LoginScreen";
import SettingsScreen from "./screens/SettingsScreen";
import TrafficScreen from "./screens/TrafficScreen";
import "./styles/screen.css";

function AuthedApp() {
  const navigate = useNavigate();

  // Lets a tap on a push notification (handled in sw.ts) route the already-open app.
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === "navigate" && typeof event.data.path === "string") {
        navigate(event.data.path);
      }
    };
    navigator.serviceWorker?.addEventListener("message", handler);
    return () => navigator.serviceWorker?.removeEventListener("message", handler);
  }, [navigate]);

  return (
    <>
      <Routes>
        <Route path="/" element={<LiveMapScreen />} />
        <Route path="/atc" element={<AtcAheadScreen />} />
        <Route path="/traffic" element={<TrafficScreen />} />
        <Route path="/flight" element={<FlightDetailsScreen />} />
        <Route path="/settings" element={<SettingsScreen />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <BottomNav />
    </>
  );
}

function Gate() {
  const { me, loading } = useAuth();

  if (loading) {
    return (
      <div className="login-screen">
        <p className="dim mono">Loading…</p>
      </div>
    );
  }

  if (!me) return <LoginScreen />;
  return <AuthedApp />;
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  );
}
