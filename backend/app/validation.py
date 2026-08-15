"""Compare detections against ground-truth annotations.

Ground truth is read in YOLO label format — one line per object:

    <class_id> <x_center> <y_center> <width> <height>

with all four box values normalised to 0–1. That is the same format the model
was trained on, so a test image's existing .txt label file can be used as-is.

Predictions are matched to ground truth greedily, highest confidence first,
each prediction taking the best still-unclaimed box above the IoU threshold.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from .errors import ApiError

Box = tuple[float, float, float, float]  # x1, y1, x2, y2


@dataclass
class GroundTruth:
    id: str
    class_id: int
    label: str
    bbox: list[float]
    matched: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Metrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    iou_threshold: float

    def to_dict(self) -> dict:
        return asdict(self)


def iou(a: Box, b: Box) -> float:
    """Intersection over union of two xyxy boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_w = min(ax2, bx2) - max(ax1, bx1)
    inter_h = min(ay2, by2) - max(ay1, by1)
    if inter_w <= 0 or inter_h <= 0:
        return 0.0

    intersection = inter_w * inter_h
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
    return intersection / union if union > 0 else 0.0


def parse_labels(
    text: str,
    image_width: int,
    image_height: int,
    names: dict[int, str],
    keep_class_ids: list[int] | None = None,
) -> list[GroundTruth]:
    """Turn a YOLO .txt label file into pixel-space boxes."""
    boxes: list[GroundTruth] = []

    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 5:
            raise ApiError(
                f"Line {line_number} of the label file has {len(parts)} values; "
                "expected at least 5 (class x_center y_center width height).",
                status=400,
            )

        try:
            class_id = int(float(parts[0]))
            cx, cy, w, h = (float(v) for v in parts[1:5])
        except ValueError as exc:
            raise ApiError(
                f"Line {line_number} of the label file is not numeric.", status=400
            ) from exc

        if keep_class_ids is not None and class_id not in keep_class_ids:
            continue

        # Normalised centre/size -> absolute corners.
        x1 = (cx - w / 2) * image_width
        y1 = (cy - h / 2) * image_height
        x2 = (cx + w / 2) * image_width
        y2 = (cy + h / 2) * image_height

        boxes.append(
            GroundTruth(
                id=f"gt{line_number}",
                class_id=class_id,
                label=names.get(class_id, str(class_id)),
                bbox=[round(v, 1) for v in (x1, y1, x2, y2)],
            )
        )

    return boxes


def evaluate(
    detections: Sequence,
    truths: list[GroundTruth],
    iou_threshold: float = 0.5,
) -> Metrics:
    """Match detections to ground truth and score the result.

    Mutates each detection (sets .matched and .iou) and each GroundTruth
    (.matched) so the UI can colour boxes by outcome.
    """
    # Highest confidence first, so a strong detection claims a box before a
    # weak one competing for the same person.
    ordered = sorted(detections, key=lambda d: d.confidence, reverse=True)

    for detection in ordered:
        best_score = 0.0
        best_truth: GroundTruth | None = None

        for truth in truths:
            if truth.matched:
                continue
            score = iou(tuple(detection.bbox), tuple(truth.bbox))
            if score >= iou_threshold and score > best_score:
                best_score = score
                best_truth = truth

        if best_truth is not None:
            best_truth.matched = True
            detection.matched = True
            detection.iou = round(best_score, 3)
        else:
            detection.matched = False
            detection.iou = None

    true_positives = sum(1 for t in truths if t.matched)
    false_positives = len(ordered) - true_positives
    false_negatives = len(truths) - true_positives

    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives)
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives)
        else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    )

    return Metrics(
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        iou_threshold=iou_threshold,
    )
