"""
Resolves which VATSIM pilot a user is currently "tracking" for the Live Map /
ATC Ahead / Flight Details screens.

Originally this was always the logged-in user's own CID. It's now generalized
so a user can track ANY callsign (their own flight, a friend's, or any pilot
on the network) — set via Settings and stored in UserSettings.tracked_callsign.

Falls back to the user's own VATSIM CID if no callsign has been set, so a
freshly logged-in user still sees their own flight by default if they're
connected under their own account.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserSettings
from app.vatsim_client import vatsim_client


async def get_tracked_callsign(db: AsyncSession, user: User) -> str | None:
    """Returns the callsign the user wants tracked, or None if nothing is
    configured and their own CID isn't currently flying either."""
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings_row = result.scalar_one_or_none()

    if settings_row and settings_row.tracked_callsign:
        return settings_row.tracked_callsign.strip().upper()

    # Fallback: use the logged-in user's own VATSIM CID, if they're online.
    own_pilot = vatsim_client.find_pilot_by_cid(int(user.vatsim_cid))
    if own_pilot:
        return own_pilot["callsign"]

    return None


def resolve_pilot(callsign: str | None) -> dict | None:
    if not callsign:
        return None
    return vatsim_client.find_pilot_by_callsign(callsign.strip().upper())
