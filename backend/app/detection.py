"""YOLO inference.

Wraps an Ultralytics model (a custom-trained .pt). The model is loaded once
per process on first use, not at import, so the server still boots when the
weights file is missing or torch isn't installed yet.

Priority is derived from confidence: a detection the model is sure about needs
no human, an uncertain one goes to the top of the review queue.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from flask import current_app

from .errors import ApiError

_model = None
_model_path: str | None = None
_lock = threading.Lock()


@dataclass
class Detection:
    id: str
    label: str
    confidence: float
    priority: str
    bbox: list[float]  # [x1, y1, x2, y2] in pixels
    frame: int | None = None
    track_id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def model_path() -> Path:
    """Resolve YOLO_MODEL_PATH against the backend root."""
    path = Path(current_app.config["YOLO_MODEL_PATH"])
    if not path.is_absolute():
        path = Path(current_app.root_path).parent / path
    return path


def model_available() -> bool:
    # is_file(), not exists(): a .pt is a zip internally, so an unpacked one
    # leaves a *directory* at this path and exists() would wrongly say yes.
    return model_path().is_file()


def get_model():
    """Load the weights once per process. Thread-safe."""
    global _model, _model_path

    path = model_path()
    if path.is_dir():
        raise ApiError(
            f"{path} is a directory, not a weights file. A .pt file is a zip "
            "archive internally, so it looks like this one was extracted. "
            "Point YOLO_MODEL_PATH at the original .pt file.",
            status=503,
        )
    if not path.is_file():
        raise ApiError(
            f"YOLO weights not found at {path}. Set YOLO_MODEL_PATH in .env "
            "or drop your .pt file there.",
            status=503,
        )

    with _lock:
        if _model is None or _model_path != str(path):
            try:
                from ultralytics import YOLO
            except ImportError as exc:  # pragma: no cover - env dependent
                raise ApiError(
                    "ultralytics is not installed. Run: pip install -r requirements.txt",
                    status=503,
                ) from exc

            _model = YOLO(str(path))
            _model_path = str(path)

    return _model


def priority_for(confidence: float, threshold: float) -> str:
    """Confident detections are low priority; uncertain ones need a human."""
    if confidence >= threshold:
        return "low"
    if confidence >= threshold * 0.7:
        return "medium"
    return "high"


def _class_filter(model) -> list[int] | None:
    """Map configured class names to the model's own class indices."""
    wanted = current_app.config["YOLO_CLASSES"]
    if not wanted:
        return None

    names: dict[int, str] = model.names
    wanted_lower = {w.strip().lower() for w in wanted}
    ids = [i for i, name in names.items() if name.lower() in wanted_lower]

    if not ids:
        raise ApiError(
            f"None of YOLO_CLASSES={wanted} exist in this model. "
            f"Available: {sorted(names.values())}",
            status=400,
        )
    return ids


def _to_detection(box, names, frame: int | None, threshold: float) -> Detection:
    confidence = float(box.conf[0])
    class_id = int(box.cls[0])
    track_id = int(box.id[0]) if getattr(box, "id", None) is not None else None

    return Detection(
        id=uuid.uuid4().hex[:12],
        label=names.get(class_id, str(class_id)),
        confidence=round(confidence, 4),
        priority=priority_for(confidence, threshold),
        bbox=[round(v, 1) for v in box.xyxy[0].tolist()],
        frame=frame,
        track_id=track_id,
    )


def detect(path: Path, kind: str) -> list[Detection]:
    """Run inference over an image or video and return detections."""
    model = get_model()
    cfg = current_app.config
    threshold = cfg["CONFIDENCE_THRESHOLD"]

    common = {
        "conf": cfg["YOLO_MIN_CONFIDENCE"],
        "iou": cfg["YOLO_IOU"],
        "device": cfg["YOLO_DEVICE"],
        "classes": _class_filter(model),
        "verbose": False,
    }

    if kind == "image":
        results = model.predict(source=str(path), **common)
        return [
            _to_detection(box, model.names, None, threshold)
            for result in results
            for box in result.boxes
        ]

    # Video: track() keeps an id per person across frames, so one person
    # walking through the clip is one row rather than one row per frame.
    results = model.track(
        source=str(path),
        stream=True,
        persist=True,
        vid_stride=cfg["VIDEO_FRAME_STRIDE"],
        **common,
    )

    best: dict[int, Detection] = {}
    untracked: list[Detection] = []

    for frame_index, result in enumerate(results):
        for box in result.boxes:
            detection = _to_detection(box, model.names, frame_index, threshold)
            if detection.track_id is None:
                untracked.append(detection)
            else:
                # Keep the frame where we saw this person most clearly.
                current = best.get(detection.track_id)
                if current is None or detection.confidence > current.confidence:
                    best[detection.track_id] = detection

    return list(best.values()) + untracked
