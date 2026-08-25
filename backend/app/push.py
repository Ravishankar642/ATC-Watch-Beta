"""
Standards-based Web Push using VAPID (RFC 8292). Works on iOS Safari
(installed to Home Screen, iOS 16.4+), Android Chrome/Firefox, and desktop
browsers with no proprietary push service required.

The VAPID private key NEVER leaves this backend. The public key is served
to the frontend via /api/push/vapid-public-key so the client can create a
PushSubscription; only the resulting subscription (endpoint + public keys
for that subscription) is stored server-side.
"""
from __future__ import annotations

import asyncio
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import PushSubscription

logger = logging.getLogger("vatsim.push")
settings = get_settings()


async def send_push_to_user(db: AsyncSession, user_id: str, title: str, body: str, data: dict | None = None) -> None:
    result = await db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))
    subscriptions = result.scalars().all()

    if not subscriptions:
        logger.info("No push subscriptions for user %s — skipping send", user_id)
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "data": data or {},
    })

    dead_subscription_ids = []
    for sub in subscriptions:
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_CLAIM_EMAIL},
            )
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            logger.warning("Push failed for subscription %s (status=%s): %s", sub.id, status, exc)
            if status in (404, 410):
                # Subscription expired or was unsubscribed client-side — clean it up.
                dead_subscription_ids.append(sub.id)

    if dead_subscription_ids:
        for sub in subscriptions:
            if sub.id in dead_subscription_ids:
                await db.delete(sub)
        await db.commit()
