"""
Background loop that, on each VATSIM feed refresh, evaluates ATC relevance
for every user who has push notifications enabled and sends any notifications
the AlertTracker decides are warranted. Runs independently of individual
frontend requests so notifications arrive even when the app isn't open.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.alert_tracker import evaluate_alerts
from app.atc_engine import predict_relevant_controllers
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.flight_resolver import resolve_pilot
from app.models import PushSubscription, User, UserSettings
from app.push import send_push_to_user
from app.route_resolver import resolve_route_endpoints
from app.vatsim_client import vatsim_client
from app.vatspy_data import vatspy_boundaries

logger = logging.getLogger("vatsim.alert_job")
settings = get_settings()

async def run_forever() -> None:
    while True:
        try:
            await asyncio.sleep(settings.VATSIM_POLL_INTERVAL_SECONDS)
            await _evaluate_all_users()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error in alert evaluation loop")


async def _evaluate_all_users() -> None:
    snapshot = vatsim_client.snapshot
    if snapshot.is_stale or not snapshot.fetched_at:
        return  # never alert on stale data

    await vatspy_boundaries.load()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User, UserSettings)
            .join(UserSettings, UserSettings.user_id == User.id)
            .where(UserSettings.notifications_enabled.is_(True))
        )
        rows = result.all()

        for user, user_settings in rows:
            callsign = (user_settings.tracked_callsign or "").strip().upper() or None
            pilot = resolve_pilot(callsign) if callsign else vatsim_client.find_pilot_by_cid(int(user.vatsim_cid))
            if pilot is None:
                continue  # nothing being tracked, or the tracked callsign isn't currently online

            sub_check = await db.execute(select(PushSubscription).where(PushSubscription.user_id == user.id))
            if not sub_check.scalars().first():
                continue

            # Same reasoning as atc.py: current position -> arrival only.
            # Departure is excluded — for an airborne aircraft it's behind
            # the aircraft, not ahead, and creates a backtracking route.
            flight_plan = pilot.get("flight_plan")
            flight_plan = flight_plan if isinstance(flight_plan, dict) else {}
            route_points: list[tuple[float, float]] = [(pilot["latitude"], pilot["longitude"])]
            route_points += resolve_route_endpoints(None, flight_plan.get("arrival"))

            predictions = predict_relevant_controllers(
                pilot=pilot,
                route_points=route_points,
                controllers=vatsim_client.all_controllers(),
            )

            notifications = await evaluate_alerts(db, user.id, user_settings, predictions)

            for note in notifications:
                await send_push_to_user(
                    db, user.id, note["title"], note["body"],
                    data={"screen": "atc-ahead", "controller": note["controller_callsign"]},
                )
                logger.info("Sent '%s' alert for %s to user %s", note["type"], note["controller_callsign"], user.vatsim_cid)
