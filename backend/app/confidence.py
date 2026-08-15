"""Wiring between YOLO detections and the confidence re-evaluation loop.

`confidence_loop.tag_detections` owns the decision logic. This module only
supplies the two things it needs from the outside world: a way to get the
pixels for a detection (`crop_fn`) and a model that re-scores them
(`ReEvaluator`), then copies the verdicts back onto our own Detection objects.

Crops are read from the thumbnails already written during detection, which is
what makes this work for video too: each detection's crop came from its own
frame, so there is no single "the image" to slice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from flask import current_app

from . import confidence_loop as loop
from . import detection as detection_module
from . import storage


class YoloReEvaluator:
    """Re-score a cropped region by running the detector over just that crop.

    A crop is upscaled to the model's input size, so a person who was small and
    ambiguous in the full frame gets a much closer look.
    """

    def __init__(self, model, class_ids: list[int] | None, device: str):
        self.model = model
        self.class_ids = class_ids
        self.device = device

    def __call__(self, crop: Any, detection: loop.Detection) -> float:
        if crop is None or getattr(crop, "size", 0) == 0:
            return 0.0

        results = self.model.predict(
            source=crop,
            conf=0.01,  # deliberately permissive: we want the score, not a filter
            classes=self.class_ids,
            device=self.device,
            verbose=False,
        )

        best = 0.0
        for result in results:
            for box in result.boxes:
                best = max(best, float(box.conf[0]))
        return best


def _crop_reader(detections: Sequence, crops_dir: Path):
    """crop_fn that loads the thumbnail written for each detection."""
    import cv2

    def crop_fn(_image: Any, det: loop.Detection):
        ours = detections[det.source_index]
        path = crops_dir / f"{ours.id}.jpg"
        if not path.exists():
            return None
        return cv2.imread(str(path))

    return crop_fn


def apply(detections: Sequence, upload_id: str) -> list[loop.TagResult]:
    """Run the loop over these detections and annotate them in place."""
    if not detections or not current_app.config["REEVAL_ENABLED"]:
        return []

    cfg = current_app.config
    model = detection_module.get_model()

    queue = [
        loop.Detection(
            bbox=tuple(d.bbox),
            confidence=d.confidence,
            label=d.label,
            source_index=index,
        )
        for index, d in enumerate(detections)
    ]

    results = loop.tag_detections(
        image=None,  # unused: crop_fn reads per-detection thumbnails instead
        detections=queue,
        reevaluate=YoloReEvaluator(
            model,
            detection_module._class_filter(model),
            cfg["YOLO_DEVICE"],
        ),
        conf_threshold=cfg["REEVAL_CONF_THRESHOLD"],
        reeval_delta_pct=cfg["REEVAL_DELTA_PCT"],
        delta_mode=cfg["REEVAL_DELTA_MODE"],
        crop_fn=_crop_reader(detections, storage.crops_dir(upload_id)),
    )

    for result in results:
        ours = detections[result.detection.source_index]
        ours.status = result.status.value
        ours.reeval_confidence = (
            round(result.reeval_confidence, 4)
            if result.reeval_confidence is not None
            else None
        )
        ours.delta_pct = (
            round(result.delta_pct, 1) if result.delta_pct is not None else None
        )

    return results
