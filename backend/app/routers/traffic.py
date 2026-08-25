from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.flight_resolver import get_tracked_callsign, resolve_pilot
from app.geo_utils import haversine_nm
from app.models import User, UserSettings
from app.schemas import TrafficAircraftOut, TrafficOut
from app.vatsim_client import vatsim_client

router = APIRouter(prefix="/api/traffic", tags=["traffic"])


@router.get("", response_model=TrafficOut)
async def get_traffic(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    radius_nm: int | None = Query(default=None, ge=1, le=1000),
    altitude_diff_ft: int | None = Query(default=None, ge=0, le=60000),
):
    await vatsim_client.refresh()
    snapshot = vatsim_client.snapshot
    tracked_callsign = await get_tracked_callsign(db, user)
    me = resolve_pilot(tracked_callsign)

    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings_row = result.scalar_one_or_none()
    effective_radius = radius_nm or (settings_row.traffic_radius_nm if settings_row else 150)
    effective_alt_diff = altitude_diff_ft if altitude_diff_ft is not None else (
        settings_row.altitude_filter_ft if settings_row else 10000
    )

    aircraft: list[TrafficAircraftOut] = []
    for p in vatsim_client.all_pilots():
        if me and p["callsign"] == me["callsign"]:
            continue
        if p.get("latitude") is None or p.get("longitude") is None:
            continue

        distance_nm = None
        relative_altitude_ft = None
        if me:
            distance_nm = round(haversine_nm(me["latitude"], me["longitude"], p["latitude"], p["longitude"]), 1)
            relative_altitude_ft = p.get("altitude", 0) - me.get("altitude", 0)
            if distance_nm > effective_radius:
                continue
            if abs(relative_altitude_ft) > effective_alt_diff:
                continue

        flight_plan = p.get("flight_plan") or {}
        aircraft.append(TrafficAircraftOut(
            cid=p["cid"],
            callsign=p["callsign"],
            latitude=p["latitude"],
            longitude=p["longitude"],
            altitude=p.get("altitude", 0),
            groundspeed=p.get("groundspeed", 0),
            heading=p.get("heading", 0),
            aircraft_short=flight_plan.get("aircraft_short"),
            departure=flight_plan.get("departure"),
            arrival=flight_plan.get("arrival"),
            route=flight_plan.get("route"),
            distance_nm=distance_nm,
            relative_altitude_ft=relative_altitude_ft,
        ))

    aircraft.sort(key=lambda a: a.distance_nm if a.distance_nm is not None else 1e9)

    return TrafficOut(
        aircraft=aircraft,
        last_updated=datetime.fromtimestamp(snapshot.fetched_at, tz=timezone.utc) if snapshot.fetched_at else None,
        data_stale=snapshot.is_stale,
    )
