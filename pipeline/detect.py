"""
pipeline/detect.py
Person detection using YOLOv8n.
process_frame returns only class_id==0 (person) detections.
"""
from __future__ import annotations

from typing import Any

import numpy as np

_model = None


def _get_model(weights: str = "yolov8n.pt"):
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(weights)
    return _model


def process_frame(
    frame: np.ndarray,
    model=None,
    conf_threshold: float = 0.25,
) -> list[dict]:
    """
    Run YOLOv8n inference on a single frame.
    Returns list of {bbox:[x1,y1,x2,y2], confidence:float, class_id:int}
    filtered to persons only (class_id == 0).
    Low-confidence detections are NOT suppressed — they are returned with
    a confidence_band flag set to "LOW".
    """
    if model is None:
        model = _get_model()

    results = model(frame, conf=conf_threshold, verbose=False)
    detections = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for box in boxes:
            cls = int(box.cls[0])
            if cls != 0:  # person only
                continue
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            band = "HIGH" if conf >= 0.6 else ("MED" if conf >= 0.4 else "LOW")
            detections.append({
                "bbox": [x1, y1, x2, y2],
                "confidence": conf,
                "class_id": cls,
                "confidence_band": band,
            })
    return detections
