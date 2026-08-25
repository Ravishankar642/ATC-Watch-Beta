"""
Attempts to turn a filed route string ("DCT ABCDE Y123 FGHIJ DCT") plus
departure/arrival ICAO codes into an ordered list of (lat, lon) waypoints
for map drawing and FIR-intersection prediction.

Full resolution requires a navdata database (airports, VOR/NDB, named
fixes, airways) which is outside the scope of this MVP. Rather than
inventing coordinates for unresolved fixes, this module:
  1. Resolves what it can from the small bundled airport reference table.
  2. Falls back to `project_route_ahead()` (a simple great-circle
     projection along current heading) for prediction purposes when the
     filed route can't be geocoded.
  3. Never draws a fabricated route on the map — the frontend only draws
     waypoints this resolver actually returns with real coordinates, and
     otherwise shows "Route waypoints unavailable" rather than a guess.

TODO (future improvement, see README "Roadmap"): integrate a full
navdata source (e.g. X-Plane earth_fix.dat / earth_awy.dat or a
DFS/NASR extract) to resolve named fixes and airways properly.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger("vatsim.route_resolver")

AIRPORTS_CSV = Path(__file__).parent / "data" / "airports.csv"

_airport_cache: dict[str, tuple[float, float]] | None = None


def _load_airports() -> dict[str, tuple[float, float]]:
    global _airport_cache
    if _airport_cache is not None:
        return _airport_cache
    _airport_cache = {}
    if AIRPORTS_CSV.exists():
        with open(AIRPORTS_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                icao = row.get("icao", "").strip().upper()
                try:
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                except (KeyError, ValueError):
                    continue
                if icao:
                    _airport_cache[icao] = (lat, lon)
    else:
        logger.warning("No bundled airport reference table at %s — departure/arrival endpoints unresolved", AIRPORTS_CSV)
    return _airport_cache


def resolve_route_endpoints(departure_icao: str | None, arrival_icao: str | None) -> list[tuple[float, float]]:
    """Returns whatever real endpoint coordinates we can resolve (0, 1, or 2 points)."""
    airports = _load_airports()
    points = []
    if departure_icao and departure_icao.upper() in airports:
        points.append(airports[departure_icao.upper()])
    if arrival_icao and arrival_icao.upper() in airports:
        points.append(airports[arrival_icao.upper()])
    return points
