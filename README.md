# AI Road Damage Detection

> Web-based prototype for detecting road damage (potholes, cracks, surface damage) using **YOLOv8**, with **live camera** and **video upload** modes sharing a single trained model, plus a simulated **LoRa-inspired V2V** hazard broadcast layer.

---

## Features

- **Live Camera Detection** — real-time inference from device camera via WebSocket, with bounding-box overlays, confidence scores, FPS counter, and GPS tagging.
- **Video Upload & Analysis** — upload MP4/AVI/MOV/WebM for offline frame-by-frame analysis. Produces an annotated output video and a full detection log.
- **V2V Hazard Mesh** — simulated LoRa-inspired broadcast layer. High-confidence detections are pushed to all connected devices in real time.
- **Resumable Training** — bundled dataset (1000 images, 3 classes) with a training script that supports stop-and-resume via checkpoints.

---

## Project Structure

```
roadai/
├── backend/                    FastAPI application (deployed on Render)
│   ├── app/
│   │   ├── main.py             App entry point
│   │   ├── routers/
│   │   │   ├── live.py         WebSocket — live camera detection
│   │   │   ├── video.py        REST — video upload, processing, results
│   │   │   └── v2v.py          WebSocket — V2V hazard mesh
│   │   └── services/
│   │       ├── detector.py     Shared YOLOv8 model (singleton)
│   │       └── v2v_hub.py      In-memory pub/sub broadcast hub
│   ├── data/                   Bundled training dataset
│   │   ├── dataset.yaml        Dataset config (3 classes)
│   │   ├── images/             800 train + 200 val images
│   │   └── labels/             YOLO-format label files
│   ├── model/                  Trained weights (road_damage.pt)
│   ├── train.py                Training script with resume support
│   ├── Procfile                Render process declaration
│   └── requirements.txt        Python dependencies
│
├── frontend/                   Plain HTML/CSS/JS (deployed on Vercel)
│   ├── index.html              Dashboard page
│   ├── live.html               Live camera detection page
│   ├── upload.html             Video upload & analysis page
│   ├── css/style.css           Design system & all styles
│   ├── js/
│   │   ├── config.js           Backend URL config (edit for deployment)
│   │   └── common.js           Shared utilities & V2V panel
│   └── vercel.json             Vercel deployment config
│
└── render.yaml                 Render Blueprint (auto-deploy)
```

---

## Local Development

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000** — the backend serves both the API and the frontend locally.

> On first run without `model/road_damage.pt`, Ultralytics auto-downloads a stock `yolov8n.pt` so you can test the full pipeline. Detections from the fallback model are labeled `untrained_class_N`.

---

## Deployment

### Step 1 — Deploy Backend on Render

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo (`AI-Road-Damage-V2V`)
3. Configure:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free (or paid for better performance)
4. Click **Deploy** — wait for it to go live
5. Copy your Render URL (e.g. `https://ai-road-damage-v2v.onrender.com`)

### Step 2 — Deploy Frontend on Vercel

1. Open `frontend/js/config.js` and set your Render URL:
   ```js
   const BACKEND_URL = "https://ai-road-damage-v2v.onrender.com";
   ```
2. Commit and push the change
3. Go to [vercel.com](https://vercel.com) → **New Project** → import your repo
4. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Other
5. Click **Deploy**
6. Your frontend is live! Open the Vercel URL.

### Step 3 — Verify

- Open the Vercel URL → Dashboard should load
- Click **Live Camera** → should connect to Render backend via WebSocket
- Click **Upload Video** → should upload to Render and show progress
- Open `/health` on your Render URL → should return `{"status": "ok"}`

---

## Training the Model

The bundled dataset has **3 classes**:

| Class ID | Name     | Severity |
|----------|----------|----------|
| 0        | pothole  | high     |
| 1        | crack    | medium   |
| 2        | damage   | high     |

```bash
cd backend

# Start fresh training
python train.py --device cpu --epochs 80

# Stop anytime with Ctrl+C (checkpoints saved every epoch)

# Resume from where you stopped
python train.py --resume --device cpu
```

| File | Purpose |
|------|---------|
| `runs/road_damage/train/weights/last.pt` | Saved every epoch — used for resuming |
| `runs/road_damage/train/weights/best.pt` | Best validation score |
| `model/road_damage.pt` | Copy of best — loaded by the app |

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

## Testing the V2V Mesh

Open **two browser tabs** (or two devices on the same network). Each tab gets its own `device_id`. Run live detection or upload a video in one tab — confirmed hazards (confidence ≥ 0.5) appear in the other tab's V2V panel in real time.

---

## Future Work

- **CARLA Integration** — the detector's interface is generic enough for a CARLA camera feed.
- **Real LoRa Hardware** — `v2v_hub.py`'s `broadcast()` is the single place to swap for serial LoRa writes.
- **Database Persistence** — replace in-memory job store for production deployments.
