"""
Loads FIR/sector boundary polygons from the official VATSpy data project
(https://github.com/vatsimnetwork/vatspy-data-project) so route/airspace
intersection is based on real published boundaries — never invented shapes.

Boundaries.geojson is fetched once at startup and cached to disk; refresh
periodically (e.g. daily) since VATSpy data changes infrequently.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx
from shapely.geometry import Point, shape

from app.config import get_settings

logger = logging.getLogger("vatsim.vatspy")
settings = get_settings()

CACHE_PATH = Path(__file__).parent / "data" / "boundaries_cache.geojson"
REFRESH_INTERVAL_SECONDS = 24 * 3600


class VatspyBoundaries:
    def __init__(self) -> None:
        self._features: list[dict] = []  # {"icao": str, "callsign_prefix": str, "polygon": shapely geometry}
        self._loaded_at: float = 0.0

    async def load(self, force: bool = False) -> None:
        if not force and self._features and (time.time() - self._loaded_at) < REFRESH_INTERVAL_SECONDS:
            return

        geojson = await self._get_geojson()
        features = []
        for feat in geojson.get("features", []):
            props = feat.get("properties", {})
            try:
                geom = shape(feat["geometry"])
            except Exception:
                continue
            features.append({
                "id": props.get("id") or props.get("icao") or props.get("oceanic") or "UNKNOWN",
                "properties": props,
                "geometry": feat["geometry"],
                "polygon": geom,
            })
        self._features = features
        self._loaded_at = time.time()
        logger.info("Loaded %d FIR/sector boundary polygons", len(features))

    async def _get_geojson(self) -> dict:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(settings.VATSPY_BOUNDARIES_URL)
                resp.raise_for_status()
                data = resp.json()
            try:
                CACHE_PATH.write_text(json.dumps(data))
            except OSError:
                # Vercel's function bundle is read-only; the in-memory copy is
                # still valid for the lifetime of the warm function instance.
                logger.info("Boundary cache is read-only; using in-memory data")
            return data
        except Exception as exc:
            logger.warning("Failed to fetch VATSpy boundaries live (%s), trying cache", exc)
            if CACHE_PATH.exists():
                return json.loads(CACHE_PATH.read_text())
            logger.error("No boundary data available (no cache, fetch failed)")
            return {"type": "FeatureCollection", "features": []}

    def fir_at_point(self, lat: float, lon: float) -> dict | None:
        """Return the boundary feature containing this point, or None if unknown."""
        pt = Point(lon, lat)
        for feat in self._features:
            if feat["polygon"].contains(pt):
                return feat
        return None

    def firs_intersecting_route(self, route_points: list[tuple[float, float]]) -> list[dict]:
        """Given an ordered list of (lat, lon) points describing a route, return the
        boundary features it passes through, in order of first entry, deduplicated."""
        if len(route_points) < 2:
            single = self.fir_at_point(*route_points[0]) if route_points else None
            return [single] if single else []

        from shapely.geometry import LineString
        line = LineString([(lon, lat) for lat, lon in route_points])

        hits: list[tuple[float, dict]] = []
        for feat in self._features:
            if feat["polygon"].intersects(line):
                inter = feat["polygon"].intersection(line)
                # distance along the route to first intersection, for ordering
                try:
                    first_point = list(inter.coords)[0] if hasattr(inter, "coords") and len(inter.coords) else None
                except Exception:
                    first_point = None
                if first_point is None:
                    # fall back to distance to polygon centroid projected onto line
                    dist = line.project(feat["polygon"].centroid)
                else:
                    dist = line.project(Point(first_point))
                hits.append((dist, feat))

        hits.sort(key=lambda h: h[0])
        seen_ids = set()
        ordered = []
        for _, feat in hits:
            if feat["id"] in seen_ids:
                continue
            seen_ids.add(feat["id"])
            ordered.append(feat)
        return ordered

    def online_coverage_geojson(self, controllers: list[dict]) -> dict:
        """Return online parent-FIR/sector polygons for the map overlay."""
        online_by_prefix: dict[str, list[dict]] = {}
        for controller in controllers:
            prefix = controller.get("callsign", "").split("_", 1)[0]
            if prefix:
                online_by_prefix.setdefault(prefix, []).append(controller)

        features = []
        for feature in self._features:
            boundary_id = feature["id"]
            parent_id = boundary_id.split("-", 1)[0]
            matches = online_by_prefix.get(boundary_id, []) or online_by_prefix.get(parent_id, [])
            if not matches:
                continue
            owner = min(matches, key=lambda c: c.get("facility", 99))
            features.append({
                "type": "Feature",
                "geometry": feature["geometry"],
                "properties": {
                    "boundary_id": boundary_id,
                    "callsign": owner.get("callsign", parent_id),
                    "frequency": owner.get("frequency", ""),
                    "facility": owner.get("facility", 0),
                },
            })
        return {"type": "FeatureCollection", "features": features}


vatspy_boundaries = VatspyBoundaries()
