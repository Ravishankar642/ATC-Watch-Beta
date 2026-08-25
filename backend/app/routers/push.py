from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import PushSubscription, User, UserSettings
from app.push import send_push_to_user
from app.schemas import PushSubscriptionIn

router = APIRouter(prefix="/api/push", tags=["push"])
settings = get_settings()


@router.get("/vapid-public-key")
async def vapid_public_key():
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="VAPID keys not configured on server. See README for setup.")
    return {"publicKey": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe")
async def subscribe(payload: PushSubscriptionIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint))
    existing = result.scalar_one_or_none()

    if existing:
        existing.p256dh = payload.keys.get("p256dh", "")
        existing.auth = payload.keys.get("auth", "")
        existing.user_agent = payload.user_agent
        existing.user_id = user.id
    else:
        db.add(PushSubscription(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.get("p256dh", ""),
            auth=payload.keys.get("auth", ""),
            user_agent=payload.user_agent,
        ))

    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user.id))
    user_settings = result.scalar_one_or_none()
    if user_settings:
        user_settings.notifications_enabled = True

    await db.commit()
    return {"status": "subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(endpoint: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        await db.delete(sub)
        await db.commit()
    return {"status": "unsubscribed"}


@router.post("/test")
async def send_test_push(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Lets the Settings screen send itself a test notification to confirm the pipeline works end-to-end."""
    await send_push_to_user(db, user.id, "ATC Watch Beta", "Test notification — push is working.", {"screen": "settings"})
    return {"status": "sent"}
