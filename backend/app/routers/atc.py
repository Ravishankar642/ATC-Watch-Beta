from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.atc_engine import predict_relevant_controllers
from app.database import get_db
from app.deps import get_current_user
from app.flight_resolver import get_tracked_callsign, resolve_pilot
from app.models import User
from app.schemas import AtcAheadOut, PredictedControllerOut
from app.vatsim_client import vatsim_client
from app.vatspy_data import vatspy_boundaries

router = APIRouter(prefix="/api/atc", tags=["atc"])


@router.get("/ahead", response_model=AtcAheadOut)
async def atc_ahead(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await vatsim_client.refresh()
    snapshot = vatsim_client.snapshot
    callsign = await get_tracked_callsign(db, user)
    pilot = resolve_pilot(callsign)

    if pilot is None:
        return AtcAheadOut(current=None, upcoming=[], last_updated=None, data_stale=snapshot.is_stale)

    await vatspy_boundaries.load()

    # The VATSIM feed only exposes filed fixes and airways as text.  Until
    # navdata is available, use a heading-based projection rather than imply
    # that a straight line to an endpoint is the filed route.
    route_points: list[tuple[float, float]] = []

    predictions = predict_relevant_controllers(
        pilot=pilot,
        route_points=route_points,
        controllers=vatsim_client.all_controllers(),
    )

    current = next((p for p in predictions if p.is_current), None)
    upcoming = [p for p in predictions if not p.is_current]

    def to_out(p) -> PredictedControllerOut:
        return PredictedControllerOut(
            callsign=p.callsign,
            frequency=p.frequency,
            facility=p.facility,
            online=p.online,
            distance_nm=p.distance_nm,
            eta_minutes=p.eta_minutes,
            route_entry_point=p.route_entry_point,
            is_current=p.is_current,
            reason=p.reason,
            logged_on_minutes=p.logged_on_minutes,
        )

    return AtcAheadOut(
        current=to_out(current) if current else None,
        upcoming=[to_out(p) for p in upcoming],
        last_updated=datetime.fromtimestamp(snapshot.fetched_at, tz=timezone.utc) if snapshot.fetched_at else None,
        data_stale=snapshot.is_stale,
    )


@router.get("/coverage")
async def atc_coverage(user: User = Depends(get_current_user)):
    """Online controller coverage polygons for the live map."""
    await vatsim_client.refresh()
    await vatspy_boundaries.load()
    return vatspy_boundaries.online_coverage_geojson(vatsim_client.all_controllers())
