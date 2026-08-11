"""
Fine-tune YOLOv8 on the bundled road-damage dataset and save the result
straight into model/road_damage.pt for the app to use.

Supports RESUMING interrupted training:

    python train.py --device cpu              # start fresh
    # ... stop anytime with Ctrl+C ...
    python train.py --device cpu --resume     # continues from last checkpoint

The bundled dataset in backend/data/ has 3 classes:
    0: pothole
    1: crack
    2: damage

All trained weights are saved automatically:
    - runs/road_damage/train/weights/last.pt   (after every epoch -- used for resume)
    - runs/road_damage/train/weights/best.pt   (best validation score)
    - model/road_damage.pt                     (copy of best.pt, used by the app)
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

MODEL_OUT = Path(__file__).resolve().parent / "model" / "road_damage.pt"
DEFAULT_DATA = Path(__file__).resolve().parent / "data" / "dataset.yaml"
RUNS_DIR = Path(__file__).resolve().parent / "runs" / "road_damage"
LAST_CHECKPOINT = RUNS_DIR / "train" / "weights" / "last.pt"


def find_last_checkpoint() -> Path | None:
    """Find the most recent last.pt checkpoint across all train runs."""
    # Check the default location first
    if LAST_CHECKPOINT.exists():
        return LAST_CHECKPOINT

    # Also check numbered run directories (train2, train3, etc.)
    if RUNS_DIR.exists():
        candidates = sorted(RUNS_DIR.glob("train*/weights/last.pt"), reverse=True)
        if candidates:
            return candidates[0]

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Train YOLOv8 on the road damage dataset. "
                    "Supports resuming interrupted training with --resume."
    )
    parser.add_argument(
        "--data", default=str(DEFAULT_DATA),
        help="Path to dataset YAML (default: bundled data/dataset.yaml)"
    )
    parser.add_argument(
        "--base", default="yolov8n.pt",
        help="Base weights to fine-tune from (ignored when --resume is used)"
    )
    parser.add_argument("--epochs", type=int, default=80, help="Total epochs to train")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument(
        "--device", default="0",
        help="'0' for first GPU, 'cpu' for CPU-only, 'mps' for Apple Silicon GPU"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume training from the last saved checkpoint"
    )
    args = parser.parse_args()

    # ── Resume from checkpoint ──────────────────────────────────────
    if args.resume:
        checkpoint = find_last_checkpoint()
        if checkpoint is None:
            print("❌ No checkpoint found to resume from!")
            print("   Start a fresh training run first (without --resume).")
            return

        print(f"🔄 Resuming training from: {checkpoint}")
        model = YOLO(str(checkpoint))
        results = model.train(resume=True)

    # ── Fresh training run ──────────────────────────────────────────
    else:
        print(f"🚀 Starting fresh training")
        print(f"   Base weights : {args.base}")
        print(f"   Dataset      : {args.data}")
        print(f"   Epochs       : {args.epochs}")
        print(f"   Device       : {args.device}")
        print(f"   Batch size   : {args.batch}")
        print()

        model = YOLO(args.base)
        results = model.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            project=str(RUNS_DIR),
            name="train",
            exist_ok=True,          # reuse the same train/ directory
            save=True,              # save checkpoints
            save_period=1,          # save last.pt every epoch (safe to interrupt)
        )

    # ── Copy best weights to model/ for the app ─────────────────────
    best = Path(results.save_dir) / "weights" / "best.pt"
    last = Path(results.save_dir) / "weights" / "last.pt"

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)

    if best.exists():
        shutil.copy(best, MODEL_OUT)
        print(f"\n✅ Best weights copied to {MODEL_OUT}")
    elif last.exists():
        shutil.copy(last, MODEL_OUT)
        print(f"\n✅ Last weights copied to {MODEL_OUT} (best.pt not found)")

    print(f"   Restart the backend to pick up the new trained model.")
    print()
    print("📌 To resume training later, run:")
    print("   python train.py --resume --device cpu")


if __name__ == "__main__":
    main()
