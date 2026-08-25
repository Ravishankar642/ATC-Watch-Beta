import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """A VATSIM member, identified by their CID after VATSIM Connect OAuth."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    vatsim_cid: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    settings: Mapped["UserSettings"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    alert_states: Mapped[list["AlertState"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSettings(Base):
    """Configurable alert thresholds and filters, editable from the Settings screen."""
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), unique=True, nullable=False)

    notify_minutes_before: Mapped[int] = mapped_column(Integer, default=15)
    notify_nm_before: Mapped[int] = mapped_column(Integer, default=100)
    entry_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    controller_change_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    offline_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    traffic_radius_nm: Mapped[int] = mapped_column(Integer, default=150)
    altitude_filter_ft: Mapped[int] = mapped_column(Integer, default=10000)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tracked_callsign: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship(back_populates="settings")


class PushSubscription(Base):
    """A single browser/device Web Push subscription (per-device, VAPID-based)."""
    __tablename__ = "push_subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(String, nullable=False)
    auth: Mapped[str] = mapped_column(String, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="push_subscriptions")


class AlertState(Base):
    """
    Tracks the last notified state per (user, controller/sector) so that the
    15-second VATSIM feed refresh never spams repeat notifications for the
    same transition. This is the debounce/cooldown ledger.
    """
    __tablename__ = "alert_states"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    controller_callsign: Mapped[str] = mapped_column(String, nullable=False)
    last_alert_type: Mapped[str] = mapped_column(String, nullable=False)  # ahead|approaching|entering|change|offline
    last_alert_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="alert_states")


class OAuthState(Base):
    """Short-lived CSRF state tokens for the VATSIM Connect OAuth flow."""
    __tablename__ = "oauth_states"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    state: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
