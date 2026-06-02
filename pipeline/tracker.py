"""
pipeline/tracker.py
Use ultralytics model.track() for ByteTrack — the correct API in ultralytics 8.x.
CameraTracker wraps per-camera tracking state.
"""
from __future__ import annotations

import numpy as np


class CameraTracker:
    """
    Per-camera tracker using ultralytics model.track().
    Returns list of {track_id, bbox, confidence} per frame.
    """

    def __init__(self, camera_id: str):
        self.camera_id = camera_id

    def track_frame(self, frame: np.ndarray, model, conf_threshold: float = 0.25) -> list[dict]:
        """
        Run detection + ByteTrack on a single frame.
        Returns list of {track_id, bbox:[x1,y1,x2,y2], confidence, class_id}.
        Only returns person class (class_id == 0).
        """
        try:
            results = model.track(
                frame,
                persist=True,
                conf=conf_threshold,
                classes=[0],          # persons only
                tracker="bytetrack.yaml",
                verbose=False,
            )
        except Exception as e:
            return []

        tracks = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                if box.id is None:
                    continue
                tid = int(box.id[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cls = int(box.cls[0])
                if cls != 0:
                    continue
                band = "HIGH" if conf >= 0.6 else ("MED" if conf >= 0.4 else "LOW")
                tracks.append({
                    "track_id": tid,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class_id": cls,
                    "confidence_band": band,
                })
        return tracks
