"""Great-circle geometry helpers shared by traffic filtering and ATC prediction."""
from __future__ import annotations

import math

EARTH_RADIUS_NM = 3440.065


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_NM * math.asin(min(1, math.sqrt(a)))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    theta = math.atan2(x, y)
    return (math.degrees(theta) + 360) % 360


def destination_point(lat: float, lon: float, bearing_deg: float, distance_nm: float) -> tuple[float, float]:
    """Project a point forward along a great-circle bearing — used to synthesize a
    simple projected route ahead of the aircraft when no filed-route waypoints are usable."""
    phi1 = math.radians(lat)
    lambda1 = math.radians(lon)
    theta = math.radians(bearing_deg)
    delta = distance_nm / EARTH_RADIUS_NM

    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540) % 360 - 180


def project_route_ahead(lat: float, lon: float, heading_deg: float, groundspeed_kt: int,
                         minutes: int = 90, step_minutes: int = 5) -> list[tuple[float, float]]:
    """Build a simple projected track ahead of the aircraft along current heading.
    Used as a fallback when the filed route can't be geocoded into waypoints — this
    is clearly a projection, not real route data, and is only used for nearby-sector
    prediction, not displayed as the filed route."""
    if groundspeed_kt <= 0:
        return [(lat, lon)]
    points = [(lat, lon)]
    steps = max(1, minutes // step_minutes)
    dist_per_step = groundspeed_kt * (step_minutes / 60)
    cur_lat, cur_lon = lat, lon
    for _ in range(steps):
        cur_lat, cur_lon = destination_point(cur_lat, cur_lon, heading_deg, dist_per_step)
        points.append((cur_lat, cur_lon))
    return points
