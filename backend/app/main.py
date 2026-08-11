from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import live, video, v2v
from app.services.detector import get_detector

app = FastAPI(title="AI Road Damage Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(live.router)
app.include_router(video.router)
app.include_router(v2v.router)


@app.get("/health")
async def health():
    detector = get_detector()
    return {
        "status": "ok",
        "using_trained_weights": detector.using_trained_weights,
    }


@app.on_event("startup")
async def load_model_on_startup():
    # Load once at boot so the first request/frame isn't slow.
    detector = get_detector()
    print(f"Model loaded. Using trained weights: {detector.using_trained_weights}")


# ── Static file mounts (order matters — checked after API routes) ──
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

# Serve the frontend (plain HTML/CSS/JS).
# This MUST be the very last mount — it catches all remaining paths.
import os
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
