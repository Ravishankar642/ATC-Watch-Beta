"""
Owns the decision of WHETHER to send a notification for a given prediction,
using the AlertState table as a debounce/cooldown ledger. This is what
prevents the 15-second VATSIM refresh from spamming the same alert.

Rules:
  - Each (user, controller callsign) pair may fire a given alert_type at most
    once until a meaningful transition happens (distance/ETA crossing a
    threshold, controller going offline, a different controller taking the
    boundary, or entering the airspace).
  - A minimum cooldown between any two notifications to the same controller
    prevents rapid oscillation right at a threshold boundary.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.atc_engine import ControllerPrediction
from app.models import AlertState, UserSettings

logger = logging.getLogger("vatsim.alert_tracker")

MIN_COOLDOWN = timedelta(minutes=3)


async def evaluate_alerts(
    db: AsyncSession,
    user_id: str,
    settings: UserSettings,
    predictions: list[ControllerPrediction],
) -> list[dict]:
    """Returns a list of {type, prediction, title, body} notification payloads to send."""
    to_send: list[dict] = []
    now = datetime.now(timezone.utc)

    result = await db.execute(select(AlertState).where(AlertState.user_id == user_id))
    existing_states = {s.controller_callsign: s for s in result.scalars().all()}

    current_callsigns = {p.callsign for p in predictions}
    previously_relevant_callsigns = {
        callsign for callsign, state in existing_states.items()
        if (state.meta or {}).get("is_relevant") is True
    }
    previous_current_callsign = next((
        callsign for callsign, state in existing_states.items()
        if (state.meta or {}).get("is_current") is True
    ), None)

    for prediction in predictions:
        state = existing_states.get(prediction.callsign)

        is_controller_change = (
            settings.controller_change_alerts_enabled
            and prediction.is_current
            and previous_current_callsign is not None
            and previous_current_callsign != prediction.callsign
        )
        candidate_type = "change" if is_controller_change else _classify_alert_type(prediction, settings)

        metadata = dict(state.meta or {}) if state else {}
        metadata.update({"is_relevant": True, "is_current": prediction.is_current})
        if state:
            state.meta = metadata
        else:
            state = AlertState(
                user_id=user_id,
                controller_callsign=prediction.callsign,
                last_alert_type="seen",
                last_alert_at=now,
                meta=metadata,
            )
            db.add(state)
            existing_states[prediction.callsign] = state

        if candidate_type is None:
            continue

        if state and state.last_alert_type == candidate_type and (now - _aware(state.last_alert_at)) < MIN_COOLDOWN:
            continue  # same alert type recently sent — debounced

        if state and state.last_alert_type == candidate_type and candidate_type in ("ahead", "approaching"):
            # Only re-notify "ahead"/"approaching" once per controller unless a
            # meaningfully closer threshold has now been crossed (handled by
            # _classify_alert_type returning "approaching" after "ahead").
            continue

        title, body = _format_notification(prediction, candidate_type)
        to_send.append({
            "type": candidate_type,
            "controller_callsign": prediction.callsign,
            "title": title,
            "body": body,
        })

        state.last_alert_type = candidate_type
        state.last_alert_at = now

    # Controllers that were online/relevant last cycle but have disappeared
    # this cycle.  Always clear the durable marker; notification delivery is
    # controlled separately so enabling the setting later cannot emit stale
    # offline alerts.
    went_offline = previously_relevant_callsigns - current_callsigns
    for callsign in went_offline:
        state = existing_states.get(callsign)
        if state:
            state.meta = {**(state.meta or {}), "is_relevant": False, "is_current": False}

        if settings.offline_alerts_enabled:
            if state and state.last_alert_type == "offline" and (now - _aware(state.last_alert_at)) < MIN_COOLDOWN:
                continue
            to_send.append({
                "type": "offline",
                "controller_callsign": callsign,
                "title": f"ATC OFFLINE — {callsign}",
                "body": "This controller has gone offline.",
            })
            if state:
                state.last_alert_type = "offline"
                state.last_alert_at = now
            else:
                db.add(AlertState(
                    user_id=user_id,
                    controller_callsign=callsign,
                    last_alert_type="offline",
                    last_alert_at=now,
                    meta={"is_relevant": False, "is_current": False},
                ))

    await db.commit()
    return to_send


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _classify_alert_type(prediction: ControllerPrediction, settings: UserSettings) -> str | None:
    if prediction.distance_nm is not None and prediction.distance_nm < 3:
        return "entering" if settings.entry_alerts_enabled else None

    if prediction.eta_minutes is not None and prediction.eta_minutes <= settings.notify_minutes_before:
        return "approaching"

    if prediction.distance_nm is not None and prediction.distance_nm <= settings.notify_nm_before:
        return "ahead"

    return None


def _format_notification(prediction: ControllerPrediction, alert_type: str) -> tuple[str, str]:
    dist = f"{prediction.distance_nm:.0f} NM" if prediction.distance_nm is not None else "unknown distance"
    eta = f"~{prediction.eta_minutes:.0f} min" if prediction.eta_minutes is not None else ""

    logged_on = ""
    if prediction.logged_on_minutes is not None:
        hours, minutes = divmod(prediction.logged_on_minutes, 60)
        logged_on = f" • online {hours}h {minutes:02d}m" if hours else f" • online {minutes}m"

    if alert_type == "entering":
        return (
            f"ENTERING {prediction.callsign} AIRSPACE",
            f"{prediction.frequency} MHz{logged_on}",
        )
    if alert_type in ("ahead", "approaching"):
        return (
            f"ATC AHEAD — {prediction.callsign}",
            f"{prediction.frequency} MHz\n{dist} ahead" + (f" • {eta}" if eta else "") + logged_on,
        )
    if alert_type == "change":
        return (f"CONTROLLER CHANGE — {prediction.callsign}", f"Now covering your route on {prediction.frequency} MHz{logged_on}")
    return (f"{prediction.callsign}", prediction.frequency)
