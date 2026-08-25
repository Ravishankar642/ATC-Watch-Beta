import { NavLink } from "react-router-dom";
import "./BottomNav.css";

const TABS = [
  { to: "/", label: "Map", icon: MapIcon, end: true },
  { to: "/atc", label: "ATC Ahead", icon: TowerIcon },
  { to: "/traffic", label: "Traffic", icon: TrafficIcon },
  { to: "/flight", label: "Flight", icon: PlaneIcon },
  { to: "/settings", label: "Settings", icon: GearIcon },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      {TABS.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => `bottom-nav__item${isActive ? " is-active" : ""}`}>
          <Icon />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function MapIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M9 3 3 5v16l6-2 6 2 6-2V3l-6 2-6-2Z" strokeLinejoin="round" />
      <path d="M9 3v16M15 5v16" />
    </svg>
  );
}
function TowerIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M12 2v4M4 8h16l-2 3H6L4 8Z" strokeLinejoin="round" />
      <path d="M7 11h10l1.5 10h-13L7 11Z" strokeLinejoin="round" />
    </svg>
  );
}
function TrafficIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
      <path d="m12 7 3 5-3 5-3-5 3-5Z" strokeLinejoin="round" />
    </svg>
  );
}
function PlaneIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path
        d="M2 16.5 9 14l.5-6L4 5l1.5-2L12 6l6.5-3L20 5l-5.5 3 .5 6 7 2.5v2L15 17l-.5 4 2 1.5-1 1.5-3.5-2-3.5 2-1-1.5 2-1.5L9 17l-7-2.5v-2Z"
        strokeLinejoin="round"
      />
    </svg>
  );
}
function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3v2.2M12 18.8V21M4.9 4.9l1.6 1.6M17.5 17.5l1.6 1.6M3 12h2.2M18.8 12H21M4.9 19.1l1.6-1.6M17.5 6.5l1.6-1.6" />
    </svg>
  );
}
