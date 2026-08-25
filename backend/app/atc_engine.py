"""
ATC relevance/prediction engine.

Goal: never just "alert on nearest controller." Instead, determine which
online controller is actually going to work this flight next, by combining:
  - the aircraft's current position and filed route (or a projected track
    when no usable route geometry exists),
  - which published FIR/sector boundaries that track passes through,
  - VATSIM's top-down control convention (a more senior facility, e.g. a
    _CTR, covers airspace within its boundary even if a more specific
    _APP/_TWR position is offline — so we only surface a controller who is
    actually logged on for a given boundary, not the theoretical owner),
  - distance and ETA to the entry point of each relevant boundary.

The engine emits `ControllerPrediction` objects; a separate `AlertTracker`
owns the last-notified state per controller (see alert_state helpers) so the
15-second feed refresh never resends the same alert repeatedly.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from shapely.geometry import LineString, Point

from app.geo_utils import haversine_nm, project_route_ahead
from app.vatspy_data import vatspy_boundaries

logger = logging.getLogger("vatsim.atc_engine")

# VATSIM top-down order, most senior first. A controller callsign suffix maps
# to a facility level; when several online controllers' boundaries overlap a
# point, the most senior one currently online is the "owner" for that point.
FACILITY_SUFFIX_RANK = {
    "_FSS": 0,
    "_CTR": 1,
    "_APP": 2,
    "_DEP": 2,
    "_TWR": 3,
    "_GND": 4,
    "_DEL": 5,
}


def facility_rank(callsign: str) -> int:
    for suffix, rank in sorted(FACILITY_SUFFIX_RANK.items(), key=lambda kv: -len(kv[0])):
        if callsign.endswith(suffix):
            return rank
    return 1  # default to CTR-ish precedence for unrecognized suffixes


@dataclass
class ControllerPrediction:
    callsign: str
    frequency: str
    facility: int
    online: bool
    distance_nm: float | None
    eta_minutes: float | None
    route_entry_point: str | None
    is_current: bool
    reason: str
    logged_on_minutes: int | None = None


def _logged_on_minutes(controller: dict) -> int | None:
    value = controller.get("logon_time")
    if not value:
        return None
    try:
        logged_on = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - logged_on).total_seconds() // 60))
    except (TypeError, ValueError):
        return None


def _controller_boundary_id(controller_callsign: str) -> str:
    """VATSIM controller callsigns are typically ICAO_POSITION (e.g. VIDF_CTR).
    The boundary/FIR prefix is the ICAO segment before the first underscore."""
    return controller_callsign.split("_")[0]


def _online_controllers_by_boundary(controllers: list[dict]) -> dict[str, list[dict]]:
    mapping: dict[str, list[dict]] = {}
    for c in controllers:
        boundary_id = _controller_boundary_id(c["callsign"])
        mapping.setdefault(boundary_id, []).append(c)
    return mapping


def _candidates_for_boundary(boundary_id: str, online_by_boundary: dict[str, list[dict]]) -> list[dict]:
    """Return controllers that cover a VATSpy boundary, including its parent FIR."""
    candidates = list(online_by_boundary.get(boundary_id, []))
    parent_id = boundary_id.split("-", 1)[0]
    if parent_id != boundary_id:
        candidates.extend(online_by_boundary.get(parent_id, []))
    return list({candidate["callsign"]: candidate for candidate in candidates}.values())


def _entry_point(route_points: list[tuple[float, float]], polygon) -> tuple[float, float] | None:
    """Return the first point where an ordered route enters a boundary."""
    if polygon.covers(Point(route_points[0][1], route_points[0][0])):
        return route_points[0]

    line = LineString([(lon, lat) for lat, lon in route_points])
    intersection = line.intersection(polygon.boundary)

    def coordinates(geometry):
        if hasattr(geometry, "coords"):
            yield from geometry.coords
        elif hasattr(geometry, "geoms"):
            for part in geometry.geoms:
                yield from coordinates(part)

    points = list(coordinates(intersection))
    if not points:
        return None
    lon, lat = min(points, key=lambda point: line.project(Point(point)))
    return lat, lon


def predict_relevant_controllers(
    pilot: dict,
    route_points: list[tuple[float, float]],
    controllers: list[dict],
    current_controller_callsign: str | None = None,
) -> list[ControllerPrediction]:
    """
    Returns an ordered list of ControllerPrediction: the aircraft's current
    controller (if any) first, followed by upcoming controllers along the
    route, nearest first. Only online controllers are returned — VATSIM
    top-down coverage is used only to decide which online position "owns" a
    boundary, never to invent a controller that isn't actually logged on.
    """
    lat, lon = pilot["latitude"], pilot["longitude"]

    if not route_points or len(route_points) < 2:
        route_points = project_route_ahead(lat, lon, pilot.get("heading", 0), pilot.get("groundspeed", 0))

    firs_ahead = vatspy_boundaries.firs_intersecting_route(route_points)
    online_by_boundary = _online_controllers_by_boundary(controllers)

    predictions: list[ControllerPrediction] = []
    seen_callsigns: set[str] = set()

    for fir in firs_ahead:
        boundary_id = fir["id"]
        candidates = _candidates_for_boundary(boundary_id, online_by_boundary)
        if not candidates:
            continue  # no one online for this boundary — do not invent coverage

        # Top-down: the most senior online facility for this boundary is the owner.
        candidates_sorted = sorted(candidates, key=lambda c: facility_rank(c["callsign"]))
        owner = candidates_sorted[0]

        if owner["callsign"] in seen_callsigns:
            continue
        seen_callsigns.add(owner["callsign"])

        entry = _entry_point(route_points, fir["polygon"])
        if entry is None:
            continue
        entry_lat, entry_lon = entry
        entry_dist_nm = haversine_nm(lat, lon, entry_lat, entry_lon)
        entry_point_label = f"{entry_lat:.2f},{entry_lon:.2f}"
        is_current_guess = entry_dist_nm < 3

        gs = max(pilot.get("groundspeed", 0), 1)
        eta_minutes = round((entry_dist_nm / gs) * 60, 1) if gs > 1 else None

        is_current = (
            (current_controller_callsign is not None and owner["callsign"] == current_controller_callsign)
            or is_current_guess
        )

        reason = (
            f"Owns boundary {boundary_id} (top-down rank {facility_rank(owner['callsign'])}); "
            f"route enters at ~{entry_dist_nm:.0f} NM"
        )

        predictions.append(ControllerPrediction(
            callsign=owner["callsign"],
            frequency=owner.get("frequency", ""),
            facility=owner.get("facility", 0),
            online=True,
            distance_nm=round(entry_dist_nm, 1),
            eta_minutes=eta_minutes,
            route_entry_point=entry_point_label,
            is_current=is_current,
            reason=reason,
            logged_on_minutes=_logged_on_minutes(owner),
        ))

    current_predictions = [prediction for prediction in predictions if prediction.is_current]
    if current_predictions:
        explicit = next((p for p in current_predictions if p.callsign == current_controller_callsign), None)
        owner = explicit or min(current_predictions, key=lambda p: (facility_rank(p.callsign), p.callsign))
        for prediction in current_predictions:
            prediction.is_current = prediction is owner

    predictions.sort(key=lambda p: (not p.is_current, p.distance_nm if p.distance_nm is not None else 1e9))
    return predictions
