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
    crop_url: str | None = None
    # Video only — where in the clip this frame sits, for seeking.
    time_seconds: float | None = None
    # Filled in by the confidence re-evaluation loop.
    status: str | None = None
    reeval_confidence: float | None = None
    delta_pct: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# Extra context to include around a detection's box, as a fraction of its size.
CROP_PADDING = 0.12


def _save_crop(image, detection: Detection, out_dir: Path) -> str | None:
    """Cut this detection out of the frame it appeared in. Returns the filename."""
    import cv2

    height, width = image.shape[:2]
    x1, y1, x2, y2 = detection.bbox
    pad_x = (x2 - x1) * CROP_PADDING
    pad_y = (y2 - y1) * CROP_PADDING

    x1 = max(0, int(x1 - pad_x))
    y1 = max(0, int(y1 - pad_y))
    x2 = min(width, int(x2 + pad_x))
    y2 = min(height, int(y2 + pad_y))

    if x2 <= x1 or y2 <= y1:
        return None

    name = f"{detection.id}.jpg"
    cv2.imwrite(str(out_dir / name), image[y1:y2, x1:x2])
    return name


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


def detect(path: Path, kind: str, upload_id: str) -> list[Detection]:
    """Run inference over an image or video and return detections.

    Each detection is also cropped out of the frame it was found in, so the
    review UI can show the person rather than the whole scene.
    """
    from . import storage

    model = get_model()
    cfg = current_app.config
    threshold = cfg["CONFIDENCE_THRESHOLD"]
    out_dir = storage.crops_dir(upload_id)

    def finish(detection: Detection, image) -> Detection:
        name = _save_crop(image, detection, out_dir)
        if name:
            detection.crop_url = f"/api/upload/{upload_id}/crops/{name}"
        return detection

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
            finish(_to_detection(box, model.names, None, threshold), result.orig_img)
            for result in results
            for box in result.boxes
        ]

    # Frame rate lets us turn a frame index into a seek position.
    import cv2

    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
    capture.release()

    stride = cfg["VIDEO_FRAME_STRIDE"]

    # A bare name like "botsort.yaml" is resolved by ultralytics itself; our
    # own file needs an absolute path.
    tracker = Path(cfg["TRACKER_CONFIG"])
    if not tracker.is_absolute() and tracker.parent != Path("."):
        tracker = Path(current_app.root_path).parent / tracker
        if not tracker.exists():
            raise ApiError(f"Tracker config not found at {tracker}.", status=503)

    # Video: track() keeps an id per person across frames, so one person
    # walking through the clip is one row rather than one row per frame.
    results = model.track(
        source=str(path),
        stream=True,
        # False resets tracker state at the start of each call. The model is
        # cached across requests, so persisting would carry track ids from a
        # previous upload into this one.
        persist=False,
        vid_stride=stride,
        tracker=str(tracker),
        **common,
    )

    # Hold the frame alongside the detection so the crop can be taken from the
    # frame where that person looked clearest, not just the last one seen.
    best: dict[int, tuple[Detection, object]] = {}
    untracked: list[Detection] = []

    for sample_index, result in enumerate(results):
        # track() only yields sampled frames, so recover the real frame number.
        frame_number = sample_index * stride

        for box in result.boxes:
            detection = _to_detection(box, model.names, frame_number, threshold)
            detection.time_seconds = round(frame_number / fps, 3) if fps else None

            if detection.track_id is None:
                untracked.append(finish(detection, result.orig_img))
                continue

            current = best.get(detection.track_id)
            if current is None or detection.confidence > current[0].confidence:
                # copy(): ultralytics may reuse the frame buffer downstream.
                best[detection.track_id] = (detection, result.orig_img.copy())

    return [finish(d, image) for d, image in best.values()] + untracked
