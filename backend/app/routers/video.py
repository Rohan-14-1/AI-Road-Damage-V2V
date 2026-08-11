"""
Uploaded-video analysis pipeline.

Runs the SAME shared detector (app.services.detector.get_detector) as
the live pipeline, frame by frame, via OpenCV. Because a full video can
take a while, processing runs as a background task and the frontend
polls /video/status/{job_id} for progress, then fetches results and the
annotated output video once done.

This represents the "offline testing/demo mode" per the spec -- hazard
events from here are tagged source="uploaded_video" when pushed to the
V2V hub, distinguishing them from the live vehicle use case.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

import cv2
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.services.detector import get_detector
from app.services.v2v_hub import hub, HazardEvent

router = APIRouter()

UPLOAD_DIR = Path("storage/uploads")
OUTPUT_DIR = Path("storage/processed")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HAZARD_CONF_FOR_V2V = 0.5

# In-memory job store -- fine for a single-process prototype.
# For production, back this with Redis or a DB.
_jobs: dict[str, dict] = {}


class JobStatus(BaseModel):
    job_id: str
    status: str  # "queued" | "processing" | "done" | "error"
    progress: float
    total_frames: int
    processed_frames: int
    detection_count: int
    output_video_url: Optional[str] = None
    error: Optional[str] = None


def _process_video(job_id: str, input_path: Path, device_id: str) -> None:
    detector = get_detector()
    job = _jobs[job_id]

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        job.update(status="error", error="Could not open video file")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

    output_path = OUTPUT_DIR / f"{job_id}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    job.update(status="processing", total_frames=total_frames)

    frame_idx = 0
    all_detections = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            detections = detector.detect(frame)
            for d in detections:
                x1, y1, x2, y2 = [int(v) for v in d.box]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                label = f"{d.damage_type.upper()} {int(d.confidence * 100)}%"
                cv2.putText(frame, label, (x1, max(y1 - 8, 0)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                all_detections.append({
                    "frame": frame_idx,
                    "timestamp_s": round(frame_idx / fps, 2),
                    **d.to_dict(),
                })

            writer.write(frame)
            frame_idx += 1
            job["processed_frames"] = frame_idx
            job["progress"] = round(frame_idx / total_frames, 3) if total_frames else 0.0
            job["detection_count"] = len(all_detections)
    finally:
        cap.release()
        writer.release()

    job["detections"] = all_detections
    job["output_video_url"] = f"/video/download/{job_id}"
    job["status"] = "done"

    # Simulated hazard events for the offline/demo mode, distinguished
    # from live-vehicle events by source="uploaded_video".
    hazards = [d for d in all_detections if d["confidence"] >= HAZARD_CONF_FOR_V2V]
    job["hazard_summary"] = hazards[:50]  # cap payload size


@router.post("/video/upload")
async def upload_video(background_tasks: BackgroundTasks,
                        file: UploadFile = File(...),
                        device_id: str = "uploader-1"):
    if not file.filename.lower().endswith((".mp4", ".avi", ".mov", ".webm")):
        raise HTTPException(400, "Unsupported video format")

    job_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{job_id}_{file.filename}"
    with open(dest, "wb") as f:
        f.write(await file.read())

    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0.0,
        "total_frames": 0,
        "processed_frames": 0,
        "detection_count": 0,
        "output_video_url": None,
        "error": None,
    }

    background_tasks.add_task(_process_video, job_id, dest, device_id)
    return {"job_id": job_id}


@router.get("/video/status/{job_id}", response_model=JobStatus)
async def video_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job_id")
    return JobStatus(**{k: job.get(k) for k in JobStatus.model_fields})


@router.get("/video/results/{job_id}")
async def video_results(job_id: str):
    job = _jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "Results not ready")
    return {
        "detections": job["detections"],
        "detection_count": job["detection_count"],
        "hazard_summary": job.get("hazard_summary", []),
    }


@router.post("/video/broadcast-hazards/{job_id}")
async def broadcast_stored_hazards(job_id: str):
    """Optional: replay this job's hazards through the V2V hub, tagged
    as offline/demo events, so the live V2V panel can show them too."""
    job = _jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "Results not ready")

    sent = 0
    for h in job.get("hazard_summary", []):
        event = HazardEvent(
            damage_type=h["damage_type"],
            confidence=h["confidence"],
            severity=h["severity"],
            source="uploaded_video",
            device_id="uploader-1",
        )
        sent += await hub.broadcast(event)
    return {"broadcast_events": len(job.get("hazard_summary", [])), "deliveries": sent}


@router.get("/video/download/{job_id}")
async def download_video(job_id: str):
    from fastapi.responses import FileResponse
    path = OUTPUT_DIR / f"{job_id}.mp4"
    if not path.exists():
        raise HTTPException(404, "Processed video not found")
    return FileResponse(path, media_type="video/mp4", filename=f"processed_{job_id}.mp4")
