from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.flight_resolver import get_tracked_callsign, resolve_pilot
from app.models import User
from app.schemas import MyFlightOut, PilotOut
from app.vatsim_client import vatsim_client

router = APIRouter(prefix="/api/flight", tags=["flight"])


@router.get("/me", response_model=MyFlightOut)
async def my_flight(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await vatsim_client.refresh()
    snapshot = vatsim_client.snapshot
    callsign = await get_tracked_callsign(db, user)
    pilot_raw = resolve_pilot(callsign)

    if pilot_raw is None:
        return MyFlightOut(connected=False, pilot=None, last_updated=None, data_stale=snapshot.is_stale)

    flight_plan = pilot_raw.get("flight_plan") or {}
    pilot = PilotOut(
        cid=pilot_raw["cid"],
        callsign=pilot_raw["callsign"],
        latitude=pilot_raw["latitude"],
        longitude=pilot_raw["longitude"],
        altitude=pilot_raw.get("altitude", 0),
        groundspeed=pilot_raw.get("groundspeed", 0),
        heading=pilot_raw.get("heading", 0),
        aircraft_short=flight_plan.get("aircraft_short"),
        departure=flight_plan.get("departure"),
        arrival=flight_plan.get("arrival"),
        route=flight_plan.get("route"),
        transponder=pilot_raw.get("transponder"),
    )

    return MyFlightOut(
        connected=True,
        pilot=pilot,
        last_updated=datetime.fromtimestamp(snapshot.fetched_at, tz=timezone.utc) if snapshot.fetched_at else None,
        data_stale=snapshot.is_stale,
    )
