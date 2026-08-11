from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.v2v_hub import hub

router = APIRouter()


@router.websocket("/ws/v2v/{device_id}")
async def v2v_channel(websocket: WebSocket, device_id: str):
    """Connect a 'device' to the simulated LoRa-inspired mesh. It will
    receive every hazard event broadcast by any other device (live or
    uploaded-video sourced). This channel is pure fan-out -- devices
    don't send anything here; hazard events originate from the live and
    video routers, which call hub.broadcast() directly."""
    await hub.connect(device_id, websocket)
    try:
        while True:
            # Keep the connection open; ping/pong handled by the client.
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(device_id)


@router.get("/v2v/status")
async def v2v_status():
    return {"connected_devices": hub.connected_count}
