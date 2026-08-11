# Trained weights go here

Drop your trained YOLOv8 weights file here as:

    model/road_damage.pt

If this file is absent, the server falls back to a stock `yolov8n.pt`
(downloaded automatically by Ultralytics on first run) purely so the
app boots and the pipeline is testable end-to-end. Swap in your real
weights trained on your road-damage dataset for real detections.

To generate this file from the bundled dataset, run:

    python train.py

Expected class names (must match `CLASS_NAMES` in
`app/services/detector.py` and `data/dataset.yaml`):

    0: pothole
    1: crack
    2: damage
