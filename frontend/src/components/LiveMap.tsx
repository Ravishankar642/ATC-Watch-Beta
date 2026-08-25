import maplibregl, { type LngLatLike, Map as MapLibreMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { AtcCoverage, MyFlight, TrafficAircraft } from "../types/api";
import "./LiveMap.css";

// Free vector basemap, no API key required. Swap for your own tile source in
// production if you need higher rate limits or custom styling.
const MAP_STYLE = "https://tiles.openfreemap.org/styles/dark";

interface Props {
  flight: MyFlight | null;
  traffic: TrafficAircraft[];
  coverage: AtcCoverage | null;
  onSelectAircraft: (aircraft: TrafficAircraft) => void;
}

export default function LiveMap({ flight, traffic, coverage, onSelectAircraft }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const ownMarkerRef = useRef<Marker | null>(null);
  const trafficMarkersRef = useRef<Map<string, Marker>>(new Map());
  const hasFlownToOwnAircraft = useRef(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [0, 20],
      zoom: 2,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Own-aircraft marker + camera follow (only auto-centers once so the user can pan freely afterward)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flight?.pilot) return;
    const { latitude, longitude, heading, callsign, altitude, groundspeed } = flight.pilot;
    const lngLat: LngLatLike = [longitude, latitude];

    if (!ownMarkerRef.current) {
      const el = document.createElement("div");
      el.className = "own-aircraft-marker aircraft-marker";
      el.innerHTML = OWN_AIRCRAFT_SVG;
      const label = document.createElement("span");
      label.className = "aircraft-marker__label";
      el.append(label);
      ownMarkerRef.current = new maplibregl.Marker({ element: el, rotationAlignment: "map" }).setLngLat(lngLat).addTo(map);
    } else {
      ownMarkerRef.current.setLngLat(lngLat);
    }
    ownMarkerRef.current.setRotation(heading);
    const el = ownMarkerRef.current.getElement();
    const label = el.querySelector(".aircraft-marker__label");
    if (label) label.textContent = callsign;
    el.title = `${callsign} • FL${Math.round(altitude / 100)} • ${groundspeed} kt`;

    if (!hasFlownToOwnAircraft.current) {
      map.flyTo({ center: lngLat, zoom: 6, duration: 1200 });
      hasFlownToOwnAircraft.current = true;
    }
  }, [flight]);

  // Traffic markers — diffed by callsign so we only touch DOM nodes that changed,
  // avoiding a full re-render of potentially hundreds of markers every 15s.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();

    for (const ac of traffic) {
      seen.add(ac.callsign);
      const lngLat: LngLatLike = [ac.longitude, ac.latitude];
      let marker = trafficMarkersRef.current.get(ac.callsign);

      if (!marker) {
        const el = document.createElement("div");
        el.className = "traffic-marker aircraft-marker";
        el.innerHTML = TRAFFIC_AIRCRAFT_SVG;
        const label = document.createElement("span");
        label.className = "aircraft-marker__label";
        el.append(label);
        marker = new maplibregl.Marker({ element: el, rotationAlignment: "map" }).setLngLat(lngLat).addTo(map);
        trafficMarkersRef.current.set(ac.callsign, marker);
      } else {
        marker.setLngLat(lngLat);
      }
      marker.setRotation(ac.heading);
      const element = marker.getElement();
      const label = element.querySelector(".aircraft-marker__label");
      if (label) label.textContent = ac.callsign;
      element.onclick = () => onSelectAircraft(ac);
      element.title = `${ac.callsign} • FL${Math.round(ac.altitude / 100)} • ${ac.groundspeed} kt`;
    }

    // Remove markers for aircraft no longer in range/online
    for (const [callsign, marker] of trafficMarkersRef.current) {
      if (!seen.has(callsign)) {
        marker.remove();
        trafficMarkersRef.current.delete(callsign);
      }
    }
  }, [traffic, onSelectAircraft]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !coverage) return;
    const updateCoverage = () => {
      const source = map.getSource("atc-coverage") as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(coverage as GeoJSON.FeatureCollection);
        return;
      }
      map.addSource("atc-coverage", { type: "geojson", data: coverage as GeoJSON.FeatureCollection });
      map.addLayer({ id: "atc-coverage-fill", type: "fill", source: "atc-coverage", paint: { "fill-color": "#28d7ff", "fill-opacity": 0.10 } });
      map.addLayer({ id: "atc-coverage-line", type: "line", source: "atc-coverage", paint: { "line-color": "#28d7ff", "line-width": 1.5, "line-opacity": 0.8 } });
    };
    if (map.isStyleLoaded()) updateCoverage(); else map.once("load", updateCoverage);
  }, [coverage]);

  return <div ref={containerRef} className="live-map" />;
}

const OWN_AIRCRAFT_SVG = `
<svg viewBox="0 0 32 32" width="34" height="34">
  <path d="M16 3 L21 15 L30 19 L21 20 L23 28 L16 25 L9 28 L11 20 L2 19 L11 15 Z"
    fill="#FFB000" stroke="#0B0E14" stroke-width="1.5" />
</svg>`;

const TRAFFIC_AIRCRAFT_SVG = `
<svg viewBox="0 0 32 32" width="22" height="22">
  <path d="M16 5 L20 15 L28 18 L20 19 L21 26 L16 24 L11 26 L12 19 L4 18 L12 15 Z"
    fill="#59F2A5" stroke="#0B0E14" stroke-width="1.3" opacity="0.9" />
</svg>`;
