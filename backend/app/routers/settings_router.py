from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserSettings
from app.schemas import UserSettingsIn, UserSettingsOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=UserSettingsOut)
async def get_settings_(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings_row = result.scalar_one_or_none()
    if settings_row is None:
        settings_row = UserSettings(user_id=user.id)
        db.add(settings_row)
        await db.commit()
        await db.refresh(settings_row)
    return settings_row


@router.put("", response_model=UserSettingsOut)
async def update_settings(payload: UserSettingsIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    settings_row = result.scalar_one_or_none()
    if settings_row is None:
        settings_row = UserSettings(user_id=user.id)
        db.add(settings_row)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "tracked_callsign" and value:
            value = value.strip().upper()
        setattr(settings_row, field, value)

    await db.commit()
    await db.refresh(settings_row)
    return settings_row
