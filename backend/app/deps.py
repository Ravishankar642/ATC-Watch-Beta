from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
_serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="session")

SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


def create_session_cookie_value(user_id: str) -> str:
    return _serializer.dumps({"user_id": user_id})


def read_session_cookie_value(value: str) -> str | None:
    try:
        data = _serializer.loads(value, max_age=SESSION_MAX_AGE_SECONDS)
        return data.get("user_id")
    except BadSignature:
        return None


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    raw = request.cookies.get(settings.SESSION_COOKIE_NAME)
    user_id = read_session_cookie_value(raw) if raw else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid")
    return user


async def get_current_user_optional(request: Request, db: AsyncSession = Depends(get_db)) -> User | None:
    raw = request.cookies.get(settings.SESSION_COOKIE_NAME)
    user_id = read_session_cookie_value(raw) if raw else None
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
