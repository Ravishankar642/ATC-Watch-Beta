export interface Pilot {
  cid: number;
  callsign: string;
  latitude: number;
  longitude: number;
  altitude: number;
  groundspeed: number;
  heading: number;
  aircraft_short: string | null;
  departure: string | null;
  arrival: string | null;
  route: string | null;
  transponder: string | null;
}

export interface MyFlight {
  connected: boolean;
  pilot: Pilot | null;
  last_updated: string | null;
  data_stale: boolean;
}

export interface PredictedController {
  callsign: string;
  frequency: string;
  facility: number;
  online: boolean;
  distance_nm: number | null;
  eta_minutes: number | null;
  route_entry_point: string | null;
  is_current: boolean;
  reason: string;
  logged_on_minutes: number | null;
}

export interface AtcAhead {
  current: PredictedController | null;
  upcoming: PredictedController[];
  last_updated: string | null;
  data_stale: boolean;
}

export interface TrafficAircraft {
  cid: number;
  callsign: string;
  latitude: number;
  longitude: number;
  altitude: number;
  groundspeed: number;
  heading: number;
  aircraft_short: string | null;
  departure: string | null;
  arrival: string | null;
  route: string | null;
  distance_nm: number | null;
  relative_altitude_ft: number | null;
}

export interface Traffic {
  aircraft: TrafficAircraft[];
  last_updated: string | null;
  data_stale: boolean;
}

export interface AtcCoverage {
  type: "FeatureCollection";
  features: GeoJSON.Feature[];
}

export interface UserSettings {
  notify_minutes_before: number;
  notify_nm_before: number;
  entry_alerts_enabled: boolean;
  controller_change_alerts_enabled: boolean;
  offline_alerts_enabled: boolean;
  traffic_radius_nm: number;
  altitude_filter_ft: number;
  notifications_enabled: boolean;
  tracked_callsign: string | null;
}

export interface Me {
  vatsim_cid: string;
  full_name: string | null;
  email: string | null;
}
