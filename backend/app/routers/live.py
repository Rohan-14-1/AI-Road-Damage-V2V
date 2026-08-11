"""
Live-camera detection pipeline.

Frontend captures frames from the device camera via <canvas>, encodes
each as a base64 JPEG, and sends it over this WebSocket at a throttled
rate (see frontend/src/pages/LiveCamera.jsx -- ~5-8 fps send rate,
independent of the camera's native fps, to keep the round trip fast).
Server runs the SAME detector used by the video-upload pipeline
(app.services.detector.get_detector) and returns detections as JSON.
Any detection above the hazard threshold is also pushed to the V2V hub
so other connected "devices" see it live.
"""
from __future__ import annotations

import base64
import time

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.detector import get_detector
from app.services.v2v_hub import hub, HazardEvent

router = APIRouter()

HAZARD_CONF_FOR_V2V = 0.5  # only broadcast confident detections as V2V hazards


def decode_frame(b64_jpeg: str) -> np.ndarray:
    raw = base64.b64decode(b64_jpeg.split(",")[-1])
    arr = np.frombuffer(raw, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


@router.websocket("/ws/live-detect/{device_id}")
async def live_detect(websocket: WebSocket, device_id: str):
    await websocket.accept()
    detector = get_detector()
    frame_count = 0
    window_start = time.time()

    try:
        while True:
            msg = await websocket.receive_json()
            # Expected: {"frame": "data:image/jpeg;base64,...", "lat": .., "lon": ..}
            frame = decode_frame(msg["frame"])
            if frame is None:
                continue

            t0 = time.time()
            detections = detector.detect(frame)
            infer_ms = round((time.time() - t0) * 1000, 1)

            frame_count += 1
            elapsed = time.time() - window_start
            fps = round(frame_count / elapsed, 1) if elapsed > 0 else 0.0

            hazards = [d for d in detections if d.confidence >= HAZARD_CONF_FOR_V2V]
            for d in hazards:
                event = HazardEvent(
                    damage_type=d.damage_type,
                    confidence=d.confidence,
                    severity=d.severity,
                    source="live",
                    device_id=device_id,
                    lat=msg.get("lat"),
                    lon=msg.get("lon"),
                )
                await hub.broadcast(event, exclude_device=device_id)

            await websocket.send_json({
                "detections": [d.to_dict() for d in detections],
                "fps": fps,
                "inference_ms": infer_ms,
                "hazard_count": len(hazards),
                "status": "ROAD DAMAGE DETECTED" if hazards else "CLEAR",
            })
    except WebSocketDisconnect:
        pass
