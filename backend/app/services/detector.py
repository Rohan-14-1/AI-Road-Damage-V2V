"""
Single shared inference service.

Both the live-camera WebSocket pipeline and the uploaded-video pipeline
call this SAME loaded model instance -- there is exactly one
RoadDamageDetector, instantiated once at process startup, so "same
trained model for both modes" is enforced structurally rather than by
convention.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

import numpy as np
from ultralytics import YOLO

MODEL_DIR = Path(__file__).resolve().parents[2] / "model"
TRAINED_WEIGHTS = MODEL_DIR / "road_damage.pt"
FALLBACK_WEIGHTS = "yolov8n.pt"  # auto-downloaded by ultralytics if trained weights are missing

# Edit these to match your training config exactly.
# Must match the `names` section in data/dataset.yaml.
CLASS_NAMES = {
    0: "pothole",
    1: "crack",
    2: "damage",
}

CONFIDENCE_THRESHOLD = float(os.getenv("DETECT_CONF_THRESHOLD", "0.35"))

# Maps a detected class to a severity bucket. Adjust to your judgement /
# to a size-based rule once you have real detections to calibrate against.
SEVERITY_BY_CLASS = {
    "pothole": "high",
    "damage": "high",
    "crack": "medium",
}


@dataclass
class Detection:
    damage_type: str
    confidence: float
    severity: str
    box: List[float]  # [x1, y1, x2, y2] in pixel coords of the input frame

    def to_dict(self) -> dict:
        return asdict(self)


class RoadDamageDetector:
    """Loads the trained model once and exposes a single detect() call
    used by every consumer (live frames, video frames)."""

    def __init__(self) -> None:
        weights_path = str(TRAINED_WEIGHTS) if TRAINED_WEIGHTS.exists() else FALLBACK_WEIGHTS
        self.using_trained_weights = TRAINED_WEIGHTS.exists()
        self.model = YOLO(weights_path)
        # Warm up so the first real request isn't slowed by lazy init.
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        self.model.predict(dummy, verbose=False)

    def detect(self, frame_bgr: np.ndarray) -> List[Detection]:
        results = self.model.predict(
            frame_bgr, conf=CONFIDENCE_THRESHOLD, verbose=False
        )[0]

        detections: List[Detection] = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()

            # If running on fallback COCO weights (no trained model yet),
            # class ids won't map to road-damage classes -- label clearly
            # rather than pretending it's a real detection.
            if self.using_trained_weights:
                damage_type = CLASS_NAMES.get(cls_id, f"class_{cls_id}")
            else:
                damage_type = f"untrained_class_{cls_id}"

            detections.append(
                Detection(
                    damage_type=damage_type,
                    confidence=round(conf, 4),
                    severity=SEVERITY_BY_CLASS.get(damage_type, "unknown"),
                    box=[round(v, 1) for v in xyxy],
                )
            )
        return detections


# Single shared instance -- import this, never instantiate RoadDamageDetector
# again elsewhere in the app.
_detector: RoadDamageDetector | None = None


def get_detector() -> RoadDamageDetector:
    global _detector
    if _detector is None:
        _detector = RoadDamageDetector()
    return _detector
