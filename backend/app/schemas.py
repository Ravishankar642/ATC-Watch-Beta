from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PilotOut(BaseModel):
    cid: int
    callsign: str
    latitude: float
    longitude: float
    altitude: int
    groundspeed: int
    heading: int
    aircraft_short: str | None = None
    departure: str | None = None
    arrival: str | None = None
    route: str | None = None
    transponder: str | None = None


class ControllerOut(BaseModel):
    cid: int
    callsign: str
    frequency: str
    facility: int
    rating: int
    name: str | None = None
    text_atis: list[str] | None = None
    logon_time: str | None = None


class MyFlightOut(BaseModel):
    connected: bool
    pilot: PilotOut | None = None
    last_updated: datetime | None = None
    data_stale: bool = False


class PredictedControllerOut(BaseModel):
    callsign: str
    frequency: str
    facility: int
    online: bool
    distance_nm: float | None = None
    eta_minutes: float | None = None
    route_entry_point: str | None = None
    is_current: bool = False
    reason: str = ""
    logged_on_minutes: int | None = None


class AtcAheadOut(BaseModel):
    current: PredictedControllerOut | None = None
    upcoming: list[PredictedControllerOut] = []
    last_updated: datetime | None = None
    data_stale: bool = False


class TrafficAircraftOut(BaseModel):
    cid: int
    callsign: str
    latitude: float
    longitude: float
    altitude: int
    groundspeed: int
    heading: int
    aircraft_short: str | None = None
    departure: str | None = None
    arrival: str | None = None
    route: str | None = None
    distance_nm: float | None = None
    relative_altitude_ft: int | None = None


class TrafficOut(BaseModel):
    aircraft: list[TrafficAircraftOut]
    last_updated: datetime | None = None
    data_stale: bool = False


class UserSettingsIn(BaseModel):
    notify_minutes_before: int | None = Field(default=None, ge=1, le=120)
    notify_nm_before: int | None = Field(default=None, ge=1, le=500)
    entry_alerts_enabled: bool | None = None
    controller_change_alerts_enabled: bool | None = None
    offline_alerts_enabled: bool | None = None
    traffic_radius_nm: int | None = Field(default=None, ge=1, le=1000)
    altitude_filter_ft: int | None = Field(default=None, ge=0, le=60000)
    notifications_enabled: bool | None = None
    tracked_callsign: str | None = None

    @field_validator("tracked_callsign")
    @classmethod
    def normalize_callsign(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            return None
        if not value.replace("-", "").isalnum() or not 2 <= len(value) <= 12:
            raise ValueError("tracked_callsign must be 2–12 letters, numbers, or hyphens")
        return value


class UserSettingsOut(BaseModel):
    notify_minutes_before: int
    notify_nm_before: int
    entry_alerts_enabled: bool
    controller_change_alerts_enabled: bool
    offline_alerts_enabled: bool
    traffic_radius_nm: int
    altitude_filter_ft: int
    notifications_enabled: bool
    tracked_callsign: str | None = None

    class Config:
        from_attributes = True


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: dict[str, str]
    user_agent: str | None = None


class MeOut(BaseModel):
    vatsim_cid: str
    full_name: str | None = None
    email: str | None = None
