# AI Road Damage Detection

> Web-based prototype for detecting road damage (potholes, cracks, surface damage) using **YOLOv8**, with **live camera** and **video upload** modes sharing a single trained model, plus a simulated **LoRa-inspired V2V** hazard broadcast layer.

---

## Features

- **Live Camera Detection** — real-time inference from device camera via WebSocket, with bounding-box overlays, confidence scores, FPS counter, and GPS tagging.
- **Video Upload & Analysis** — upload MP4/AVI/MOV/WebM for offline frame-by-frame analysis. Produces an annotated output video and a full detection log.
- **V2V Hazard Mesh** — simulated LoRa-inspired broadcast layer. High-confidence detections are pushed to all connected devices in real time.
- **Resumable Training** — bundled dataset (1000 images, 3 classes) with a training script that supports stop-and-resume via checkpoints.
- **Single Server** — FastAPI serves both the REST/WebSocket API and the frontend. No npm, no build step, one command to run.

---

## Project Structure

```
roadai/
├── backend/                    FastAPI application
│   ├── app/
│   │   ├── main.py             App entry point (also serves the frontend)
│   │   ├── routers/
│   │   │   ├── live.py         WebSocket — live camera detection
│   │   │   ├── video.py        REST — video upload, processing, results
│   │   │   └── v2v.py          WebSocket — V2V hazard mesh
│   │   └── services/
│   │       ├── detector.py     Shared YOLOv8 model (singleton)
│   │       └── v2v_hub.py      In-memory pub/sub broadcast hub
│   ├── data/                   Bundled training dataset
│   │   ├── dataset.yaml        Dataset config (3 classes)
│   │   ├── images/
│   │   │   ├── train/          800 training images
│   │   │   └── val/            200 validation images
│   │   └── labels/
│   │       ├── train/          YOLO-format label files
│   │       └── val/
│   ├── model/                  Trained weights (road_damage.pt)
│   ├── train.py                Training script with resume support
│   └── requirements.txt        Python dependencies
│
└── frontend/                   Plain HTML / CSS / JS (no framework)
    ├── index.html              Dashboard page
    ├── live.html               Live camera detection page
    ├── upload.html             Video upload & analysis page
    ├── css/
    │   └── style.css           Design system & all styles
    └── js/
        └── common.js           Shared utilities & V2V panel component
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- pip

### Installation & Run

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** — dashboard loads immediately.

> On first run without `model/road_damage.pt`, Ultralytics auto-downloads a stock `yolov8n.pt` so you can test the full pipeline end-to-end. Detections from the fallback model are labeled `untrained_class_N` so they're never mistaken for real road-damage results.

---

## Training the Model

A training script with **resume support** is provided. The bundled dataset has **3 classes**:

| Class ID | Name     | Severity |
|----------|----------|----------|
| 0        | pothole  | high     |
| 1        | crack    | medium   |
| 2        | damage   | high     |

### Commands

```bash
cd backend

# Start fresh training
python train.py --device cpu --epochs 80

# Stop anytime with Ctrl+C (checkpoints saved every epoch)

# Resume from where you stopped
python train.py --resume --device cpu
```

### Where Weights Are Saved

| File | Purpose |
|------|---------|
| `runs/road_damage/train/weights/last.pt` | Saved every epoch — used for resuming |
| `runs/road_damage/train/weights/best.pt` | Best validation score across all epochs |
| `model/road_damage.pt` | Copy of best — this is what the app loads |

After training completes, restart the backend to pick up the new weights.

---

## Testing the V2V Mesh

Open **two browser tabs** (or two devices on the same network). Each tab gets its own `device_id`. Run live detection or upload a video in one tab — confirmed hazards (confidence ≥ 0.5) appear in the other tab's V2V panel in real time.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check & model status |
| WS | `/ws/live-detect/{device_id}` | Live camera detection stream |
| POST | `/video/upload` | Upload video for analysis |
| GET | `/video/status/{job_id}` | Poll processing progress |
| GET | `/video/results/{job_id}` | Fetch detection results |
| GET | `/video/download/{job_id}` | Download annotated output video |
| POST | `/video/broadcast-hazards/{job_id}` | Replay hazards to V2V mesh |
| WS | `/ws/v2v/{device_id}` | V2V hazard broadcast channel |
| GET | `/v2v/status` | Connected device count |

---

## Architecture

| Component | File | Description |
|-----------|------|-------------|
| Shared model | `backend/app/services/detector.py` | Single YOLOv8 instance used by both live and video pipelines |
| Live detection | `frontend/live.html` + `backend/app/routers/live.py` | WebSocket frame exchange at ~6-7 fps |
| Video analysis | `frontend/upload.html` + `backend/app/routers/video.py` | Background task with progress polling |
| V2V broadcast | `frontend/js/common.js` + `backend/app/services/v2v_hub.py` | WebSocket fan-out simulating LoRa mesh |
| GPS tagging | `frontend/live.html` | `navigator.geolocation` — sent with each frame |
| Dashboard | `frontend/index.html` | Entry point with links to both modes |

---

## Future Work

- **CARLA Integration** — the detector's interface (`frame in → detections out`) is generic enough that a CARLA camera feed could plug in as another frame source.
- **Real LoRa Hardware** — `v2v_hub.py`'s `broadcast()` is the single place to swap WebSocket fan-out for a serial write to a LoRa module.
- **Database Persistence** — replace in-memory job store with SQLite/PostgreSQL for production deployments.
