"""
Polls the official VATSIM v3 data feed (regenerates every 15s server-side)
and keeps an in-memory cache so every API request doesn't hit VATSIM again.
Never invents data: if the feed is stale or unreachable, callers are told so
explicitly via `is_stale` rather than being served silently outdated info.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("vatsim.client")
settings = get_settings()


@dataclass
class VatsimSnapshot:
    raw: dict[str, Any] = field(default_factory=dict)
    fetched_at: float = 0.0
    pilots_by_cid: dict[int, dict] = field(default_factory=dict)
    pilots_by_callsign: dict[str, dict] = field(default_factory=dict)
    controllers: list[dict] = field(default_factory=list)

    @property
    def age_seconds(self) -> float:
        if not self.fetched_at:
            return float("inf")
        return time.time() - self.fetched_at

    @property
    def is_stale(self) -> bool:
        return self.age_seconds > settings.VATSIM_DATA_STALE_AFTER_SECONDS


class VatsimClient:
    """Singleton-style poller. One instance is created and started at app startup."""

    def __init__(self) -> None:
        self._snapshot = VatsimSnapshot()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._http = httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "ATC-Watch-Beta/1.0"})
        self._consecutive_failures = 0

    @property
    def snapshot(self) -> VatsimSnapshot:
        return self._snapshot

    async def start(self) -> None:
        if self._task is None:
            await self.refresh(force=True)
            self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        await self._http.aclose()

    async def _poll_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(settings.VATSIM_POLL_INTERVAL_SECONDS)
                await self.refresh(force=True)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # keep the poller alive across transient errors
                logger.exception("Unexpected error in VATSIM poll loop: %s", exc)

    async def refresh(self, force: bool = False) -> None:
        """Refresh the snapshot when needed; serverless requests share this safely."""
        if not force and not self.snapshot.is_stale:
            return
        async with self._lock:
            if not force and not self.snapshot.is_stale:
                return
            await self._refresh_once()

    async def _refresh_once(self) -> None:
        try:
            resp = await self._http.get(settings.VATSIM_DATA_URL)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            self._consecutive_failures += 1
            logger.warning("VATSIM data fetch failed (%s consecutive): %s", self._consecutive_failures, exc)
            return  # keep serving the last good snapshot; caller sees is_stale=True once it ages out

        self._consecutive_failures = 0
        pilots = data.get("pilots", [])
        controllers = [
            c for c in data.get("controllers", [])
            if c.get("facility", 0) > 0 or c.get("callsign", "").endswith(("_CTR", "_APP", "_TWR", "_GND", "_DEL", "_FSS"))
        ]

        self._snapshot = VatsimSnapshot(
            raw=data,
            fetched_at=time.time(),
            pilots_by_cid={p["cid"]: p for p in pilots if "cid" in p},
            pilots_by_callsign={p["callsign"]: p for p in pilots if "callsign" in p},
            controllers=controllers,
        )
        logger.info(
            "VATSIM snapshot refreshed: %d pilots, %d controllers",
            len(pilots), len(controllers),
        )

    def find_pilot_by_cid(self, cid: int) -> dict | None:
        return self._snapshot.pilots_by_cid.get(cid)

    def find_pilot_by_callsign(self, callsign: str) -> dict | None:
        return self._snapshot.pilots_by_callsign.get(callsign)

    def all_pilots(self) -> list[dict]:
        return list(self._snapshot.pilots_by_cid.values())

    def all_controllers(self) -> list[dict]:
        return list(self._snapshot.controllers)


vatsim_client = VatsimClient()
