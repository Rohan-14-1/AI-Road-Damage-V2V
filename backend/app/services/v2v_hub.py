"""
Simulated LoRa-inspired V2V broadcast layer.

Real LoRa is a low-bandwidth broadcast medium: any node in range hears
any message. We simulate that with a WebSocket fan-out hub: every
connected "device" gets every hazard event. To swap in real hardware
later, replace `broadcast()`'s body with a serial write to a LoRa
module and keep the same HazardEvent shape -- nothing upstream (the
detection pipelines) needs to change.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import WebSocket


@dataclass
class HazardEvent:
    damage_type: str
    confidence: float
    severity: str
    source: str  # "live" | "uploaded_video"
    device_id: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


class V2VHub:
    """In-memory pub/sub. One process only -- fine for a prototype.
    For multi-instance deployment, back this with Redis pub/sub instead."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, device_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[device_id] = ws

    def disconnect(self, device_id: str) -> None:
        self._connections.pop(device_id, None)

    async def broadcast(self, event: HazardEvent, exclude_device: Optional[str] = None) -> int:
        """Send to every connected device except the originator. Returns
        the number of devices the message reached."""
        payload = event.to_dict()
        reached = 0
        dead: list[str] = []
        for device_id, ws in self._connections.items():
            if device_id == exclude_device:
                continue
            try:
                await ws.send_json(payload)
                reached += 1
            except Exception:
                dead.append(device_id)
        for device_id in dead:
            self.disconnect(device_id)
        return reached

    @property
    def connected_count(self) -> int:
        return len(self._connections)


hub = V2VHub()
