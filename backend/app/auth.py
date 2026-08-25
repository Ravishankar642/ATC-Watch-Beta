"""
VATSIM Connect OAuth2 (authorization code flow). We never see or store the
member's VATSIM password — only the short-lived OAuth token exchange, and
only the minimal profile fields required (CID, name, email) to identify the
member's flight and manage their own settings/push subscriptions.

Register an application at https://auth.vatsim.net to obtain a client
id/secret and set VATSIM_OAUTH_REDIRECT_URI to this backend's /api/auth/callback.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import OAuthState, User

settings = get_settings()


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": settings.VATSIM_CLIENT_ID,
        "redirect_uri": settings.VATSIM_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": settings.VATSIM_OAUTH_SCOPES,
        "state": state,
    }
    return f"{settings.VATSIM_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


async def create_oauth_state(db: AsyncSession) -> str:
    state = secrets.token_urlsafe(32)
    db.add(OAuthState(state=state))
    await db.commit()
    return state


async def consume_oauth_state(db: AsyncSession, state: str) -> bool:
    result = await db.execute(select(OAuthState).where(OAuthState.state == state))
    row = result.scalar_one_or_none()
    if row is None:
        return False
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if created_at < datetime.now(timezone.utc) - timedelta(seconds=settings.OAUTH_STATE_TTL_SECONDS):
        await db.delete(row)
        await db.commit()
        return False
    await db.delete(row)
    await db.commit()
    return True


async def exchange_code_for_token(code: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            settings.VATSIM_OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.VATSIM_CLIENT_ID,
                "client_secret": settings.VATSIM_CLIENT_SECRET,
                "redirect_uri": settings.VATSIM_OAUTH_REDIRECT_URI,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            settings.VATSIM_OAUTH_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_or_create_user(db: AsyncSession, userinfo: dict) -> User:
    data = userinfo.get("data", userinfo)  # VATSIM Connect wraps payload in "data"
    cid = str(data["cid"])

    result = await db.execute(select(User).where(User.vatsim_cid == cid))
    user = result.scalar_one_or_none()

    full_name = None
    personal = data.get("personal", {})
    if personal:
        full_name = " ".join(filter(None, [personal.get("name_first"), personal.get("name_last")])) or None
    email = personal.get("email") if personal else None

    if user is None:
        from app.models import UserSettings
        user = User(vatsim_cid=cid, full_name=full_name, email=email)
        db.add(user)
        await db.flush()
        db.add(UserSettings(
            user_id=user.id,
            notify_minutes_before=settings.DEFAULT_NOTIFY_MINUTES_BEFORE,
            notify_nm_before=settings.DEFAULT_NOTIFY_NM_BEFORE,
            traffic_radius_nm=settings.DEFAULT_TRAFFIC_RADIUS_NM,
            altitude_filter_ft=settings.DEFAULT_ALTITUDE_FILTER_FT,
        ))
    else:
        user.full_name = full_name or user.full_name
        user.email = email or user.email

    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user
